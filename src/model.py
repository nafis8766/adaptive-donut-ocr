import os
import gc
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict, Any, Tuple
from transformers import VisionEncoderDecoderModel, DonutProcessor

from .router import PatchSaliencyRouter
from .tome import BipartiteTokenMerger

SELECT_MODES = ("router", "negated", "random", "ink", "stratified", "stratified_negated")

TOKEN_GRID = (80, 60)   # Swin-B at 2560x1920, total stride 32


def stratified_scores(
    scores: torch.Tensor,
    grid: Tuple[int, int] = TOKEN_GRID,
    negate: bool = False,
) -> torch.Tensor:
    """Rewrite a per-token ranking so that a GLOBAL top-K becomes a PER-ROW top-k.

    Diagnostic D2's finding: a single global top-k has no mechanism bounding
    worst-case coverage. It is free to spend the whole budget on one dense region,
    and the trained router does something like this -- its *minimum* text-line ink
    coverage is 0.000, i.e. at least one line of the page loses all of its ink,
    while its total retained ink looks unremarkable. Recall is gated by the worst
    line, not the average, so that is the failure that matters.

    A per-row budget makes starving a line structurally impossible. Rather than add
    a second selection path to `PatchSaliencyRouter` (a new code path is a new place
    for the two to diverge), this expresses stratification entirely as a monotone
    rewrite of the ranking signal, so it reuses the already-verified `select_scores`
    machinery unchanged:

        key = (gw - within_row_rank) + normalized_score

    `within_row_rank` is an integer in [0, gw), so the integer part dominates and
    the normalized score only breaks ties *within* a rank band. Global top-K with
    K = gh * k then selects exactly the top-k of every row. The bands cannot
    overlap because the score term is clamped strictly below 1.0.

    When K is not a multiple of gh the separation degrades gracefully: whole rank
    bands fill first and the remainder goes to the best scores in the next band.

    `negate` ranks by the negated score inside each row, which is the fix for a
    sign-inverted scorer. Stratification and sign are orthogonal, which is the
    point -- they can be tested independently.
    """
    B, N = scores.shape
    gh, gw = grid
    if gh * gw != N:
        raise ValueError(
            f"token grid mismatch: grid {gh}x{gw}={gh * gw} but got {N} tokens")

    s = (-scores if negate else scores).reshape(B, gh, gw)

    # Descending within-row rank: 0 = highest-scoring token in its own row.
    order = s.argsort(dim=-1, descending=True)
    rank = torch.empty_like(order)
    rank.scatter_(-1, order, torch.arange(gw, device=s.device).expand_as(order))

    lo = s.amin(dim=(1, 2), keepdim=True)
    hi = s.amax(dim=(1, 2), keepdim=True)
    s_norm = ((s - lo) / (hi - lo).clamp(min=1e-9)).clamp(0.0, 0.999)

    return ((gw - rank).to(s.dtype) + s_norm).reshape(B, N)


def patch_ink(pixel_values: torch.Tensor, num_tokens: int, stride: int = 32) -> torch.Tensor:
    """Per-token within-patch contrast on the encoder's own token grid -> (B, N).

    A learning-free proxy for "there is text here", used two ways: as the `ink`
    oracle's ranking signal, and as the acceptance metric in
    `scripts/router_score_probe.py`.

    Within-patch std rather than mean darkness because it is blind to whether Donut
    padded with black or white -- uniform padding has zero contrast either way,
    while darkness would score black padding as maximum ink. D1 confirmed the two
    proxies agree on the verdict (0.381 vs 0.343 retained).

    No un-normalization is needed: donut-base uses image_mean = image_std = 0.5 on
    every channel, so pixel_values is a single uniform affine image of luminance and
    a plain channel mean ranks identically to true grayscale.
    """
    B, _, H, W = pixel_values.shape
    gh, gw = H // stride, W // stride
    if gh * gw != num_tokens:
        raise ValueError(
            f"token grid mismatch: pixel_values {H}x{W} at stride {stride} gives "
            f"{gh}x{gw}={gh * gw} patches but the encoder emitted {num_tokens} tokens"
        )
    gray = pixel_values.mean(dim=1)                                   # (B, H, W)
    blocks = gray.unfold(1, stride, stride).unfold(2, stride, stride)  # (B, gh, gw, s, s)
    return blocks.reshape(B, gh * gw, -1).std(dim=-1)                 # (B, N)


class AdaptiveDonutOCR(nn.Module):
    """
    Adaptive Low-Token Document OCR Architecture.
    
    Combines a Swin-B vision backbone with an adaptive Patch Saliency Router and
    Bipartite Token Merging (ToMe) layer feeding into an mBART text decoder.
    """
    def __init__(
        self,
        base_model_name: str = "naver-clova-ix/donut-base",
        keep_ratio: float = 0.35,
        # 0.0, not 0.20. Twelve call sites in this repo construct the model without
        # naming merge_ratio, so a non-zero default silently turned merging ON in
        # scripts whose recorded results are read as pruning-only -- notably
        # scripts/run_nrns_rp_sweep.py (the local "+4.74 pts" decoding figures) and
        # scripts/probe_generation_determinism.py, which claims to mirror that
        # unmerged sweep. Both ran at 0.20 through the pre-2026-09-14 rank-parity
        # split. Merging is an experiment, not a baseline: it has to be asked for.
        merge_ratio: float = 0.0,
        router_reduction_dim: int = 256,
        torch_dtype: Optional[torch.dtype] = None,
        freeze_encoder: bool = True
    ):
        super().__init__()
        self.base_model_name = base_model_name
        self.keep_ratio = keep_ratio
        self.merge_ratio = merge_ratio
        self.freeze_encoder = freeze_encoder
        
        # Clean GPU memory before loading weights
        if torch.cuda.is_available():
            gc.collect()
            torch.cuda.empty_cache()
            
        dtype = torch_dtype if torch_dtype is not None else torch.float32
        
        print(f"Loading base backbone {base_model_name} (dtype={dtype})...")
        self.model = VisionEncoderDecoderModel.from_pretrained(
            base_model_name,
            low_cpu_mem_usage=True
        )
        
        # Freeze encoder to avoid multi-gigabyte activation graphs
        if freeze_encoder:
            print("Freezing Swin vision encoder (saves ~12 GB VRAM). Training Router & Decoder!")
            for param in self.model.encoder.parameters():
                param.requires_grad = False
                
        # Extract dimensions
        self.encoder_hidden_dim = self.model.config.encoder.hidden_size  # 1024 for Swin-B
        
        # 1. Trainable Saliency Scoring Head
        self.router = PatchSaliencyRouter(
            hidden_dim=self.encoder_hidden_dim,
            reduction_dim=router_reduction_dim
        )
        
        # 2. Bipartite Token Merging Module
        self.tome_merger = BipartiteTokenMerger(
            hidden_dim=self.encoder_hidden_dim
        )

    def _generate_2d_coords(self, B: int, N: int, device: torch.device, dtype: torch.dtype = torch.float32) -> torch.Tensor:
        # Determine grid size based on portrait standard (H > W)
        # N = 4800 -> H=80, W=60 (4:3 aspect ratio in portrait)
        aspect_ratio = 3.0 / 4.0
        W_grid = int(round((N * aspect_ratio) ** 0.5))
        H_grid = max(1, N // W_grid)
        
        grid_y, grid_x = torch.meshgrid(
            torch.linspace(0, 1, H_grid, device=device, dtype=dtype),
            torch.linspace(0, 1, W_grid, device=device, dtype=dtype),
            indexing="ij"
        )
        coords_2d = torch.stack([grid_x, grid_y], dim=-1).view(-1, 2)  # (H*W, 2)
        
        if coords_2d.shape[0] < N:
            pad = coords_2d[-1:].repeat(N - coords_2d.shape[0], 1)
            coords_2d = torch.cat([coords_2d, pad], dim=0)
        else:
            coords_2d = coords_2d[:N]
            
        coords = coords_2d.unsqueeze(0).expand(B, -1, -1)  # (B, N, 2)
        return coords

    def _token_grid(self, pixel_values: torch.Tensor, num_tokens: int, stride: int = 32) -> Tuple[int, int]:
        """(gh, gw) of the encoder token grid, derived from the input, not assumed.

        ToMe's checkerboard split needs the grid WIDTH to turn a raster index into
        (row, col). A wrong width is the worst kind of bug here because it is
        silent: any width still yields a valid two-colour partition, just one that
        no longer corresponds to spatial adjacency, and the output tensor looks
        exactly as it should. So derive from pixel_values like `patch_ink` does and
        let a mismatch raise, rather than trusting the TOKEN_GRID constant.
        """
        H, W = pixel_values.shape[-2], pixel_values.shape[-1]
        gh, gw = H // stride, W // stride
        if gh * gw != num_tokens:
            raise ValueError(
                f"token grid mismatch: pixel_values {H}x{W} at stride {stride} gives "
                f"{gh}x{gw}={gh * gw} patches but the encoder emitted {num_tokens} "
                f"tokens (TOKEN_GRID constant is {TOKEN_GRID})"
            )
        return (gh, gw)

    def _selection_signal(
        self,
        pixel_values: torch.Tensor,
        visual_tokens: torch.Tensor,
        select_mode: str,
    ) -> Tuple[Optional[torch.Tensor], bool]:
        """Resolve a `select_mode` name into `(select_scores, invert)` for the router.

        ONE implementation, called by BOTH `forward()` (training) and `generate()`
        (eval). It is a shared helper rather than two copies on purpose: the moment
        training and eval resolve `ink` differently, every arm of run 18 becomes
        uninterpretable and nothing would fail loudly -- the tables would still look
        ordinary. This is the same reasoning AGENTS.md applies to
        `diagnose_tome_parity.py` restating `checkerboard_color` instead of importing
        it, and to the notebook duplicating the model classes.

          router  -- the learned scores (the actual model)
          negated -- the same scores, lowest-first. D1 measured the trained router as
                     anti-correlated with ink, so this retains more text than the
                     forward direction (0.62-0.66 vs 0.34-0.38).
          random  -- uniform noise: the baseline the router must beat. Draws from the
                     ambient RNG so every image gets a fresh mask -- seed once in the
                     caller for reproducibility.
          ink     -- patch contrast: a learning-free selector. Used as an eval ORACLE
                     since run 7, and since run 18 also as a TRAINING regime, which is
                     the only way to compare it to the router without the decoder
                     co-adaptation D15 measured (pooled r=-0.702 between the router's
                     retained ink and its own margin over this mode).
          stratified / stratified_negated -- the SAME learned scores under a per-grid-
                     row budget instead of one global top-k (D2).

        Raising on an unknown mode is load-bearing, not defensive: `SELECT_MODES` is
        defined elsewhere in this file, and AGENTS.md records a verifier whose silent
        `else: {}` fallthrough reported PASS for two modes that never ran.
        """
        if select_mode not in SELECT_MODES:
            raise ValueError(f"select_mode must be one of {SELECT_MODES}, got {select_mode!r}")

        B, N = visual_tokens.shape[0], visual_tokens.shape[1]
        select_scores = None
        invert = False

        if select_mode == "negated":
            invert = True
        elif select_mode == "random":
            select_scores = torch.rand(
                B, N, device=visual_tokens.device, dtype=visual_tokens.dtype)
        elif select_mode == "ink":
            select_scores = patch_ink(pixel_values, N).to(visual_tokens.dtype)
        elif select_mode in ("stratified", "stratified_negated"):
            # Grid derived from pixel_values rather than assumed, so a non-standard
            # input raises here instead of silently stratifying over the wrong axis.
            grid = (pixel_values.shape[-2] // 32, pixel_values.shape[-1] // 32)
            raw = self.router.scorer(visual_tokens).squeeze(-1)          # (B, N)
            select_scores = stratified_scores(
                raw, grid=grid, negate=(select_mode == "stratified_negated")
            ).to(visual_tokens.dtype)

        return select_scores, invert

    def forward(
        self,
        pixel_values: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        decoder_input_ids: Optional[torch.Tensor] = None,
        keep_ratio: Optional[float] = None,
        merge_ratio: Optional[float] = None,
        select_mode: str = "router"
    ) -> Dict[str, Any]:
        k_ratio = keep_ratio if keep_ratio is not None else self.keep_ratio
        m_ratio = merge_ratio if merge_ratio is not None else self.merge_ratio

        B = pixel_values.shape[0]
        device = pixel_values.device
        
        # 1. Vision Backbone Forward
        encoder_is_frozen = not any(p.requires_grad for p in self.model.encoder.parameters())
        if encoder_is_frozen:
            with torch.no_grad():
                encoder_outputs = self.model.encoder(pixel_values)
        else:
            encoder_outputs = self.model.encoder(pixel_values)
            
        visual_tokens = encoder_outputs.last_hidden_state  # (B, N, D)
        N = visual_tokens.shape[1]
        
        # 2. 2D Coordinate Grid Injection
        coords = self._generate_2d_coords(B, N, device, visual_tokens.dtype)
        
        # 3. Stage 1: Patch Saliency Scoring & Hard Pruning
        #    `select_mode` swaps the RANKING SIGNAL only; K, the architecture and the
        #    decoder are untouched. Default "router" reproduces runs 2-14 exactly.
        #
        #    NON-DEFAULT MODES CHANGE WHAT THE DECODER IS TRAINED ON. That is the
        #    point (run 18): D15 showed the router's measured margin over `ink` is
        #    driven by the INK side of the subtraction degrading (pooled r=+0.634
        #    against the router's retained ink) rather than the router side improving
        #    (+0.083), on a selection that is byte-identical across checkpoints. So
        #    the margin substantially measures decoder specialization, and the only
        #    way to separate that from selection quality is to train an arm under the
        #    free selector and compare each decoder in its OWN regime.
        #
        #    Consequence worth stating: under any mode except "router", `select_scores`
        #    is not None, so `PatchSaliencyRouter` skips the STE (router.py:92) and the
        #    scorer receives NO task gradient -- selection is not being learned, which
        #    is exactly what a "free selector" arm means. The scorer still trains if
        #    the ink-BCE auxiliary is on, and that is harmless because nothing in this
        #    forward pass reads the scorer's output when an override is supplied.
        select_scores, invert = self._selection_signal(
            pixel_values, visual_tokens, select_mode)
        selected_tokens, scores, topk_indices, pruned_coords = self.router(
            visual_tokens,
            keep_ratio=k_ratio,
            coords=coords,
            use_ste=self.training,
            select_scores=select_scores,
            invert=invert
        )
        
        # 4. Stage 2: Bipartite Token Merging (ToMe)
        #    `topk_indices` is not optional: the router returns tokens sorted by
        #    DESCENDING SCORE, so a token's position in `selected_tokens` says
        #    nothing about where it sits on the page. ToMe splits A/B by the
        #    checkerboard colour of the ORIGINAL raster position, which is what
        #    `topk_indices` carries. Grid resolved only when merging is actually
        #    on, so a non-standard input still runs at merge_ratio=0.
        tome_grid = self._token_grid(pixel_values, N) if m_ratio > 0.0 else None
        compressed_tokens, final_coords = self.tome_merger(
            selected_tokens,
            merge_ratio=m_ratio,
            coords=pruned_coords,
            orig_idx=topk_indices,
            token_grid=tome_grid
        )
        
        M = compressed_tokens.shape[1]

        # 5. Autoregressive Text Decoder Forward (mBART)
        #    self.model.decoder is an MBartForCausalLM, which does NOT shift
        #    labels internally. Feeding decoder_input_ids == labels and letting
        #    the decoder compute the loss trains the model to COPY the current
        #    token (next-token loss -> 0) and collapses generation to a single
        #    repeated token. We instead take raw logits and compute the loss
        #    with an explicit right-shift: position t predicts token t+1.
        decoder_outputs = self.model.decoder(
            input_ids=decoder_input_ids,
            encoder_hidden_states=compressed_tokens,
            return_dict=True
        )
        logits = decoder_outputs.logits

        loss = None
        if labels is not None:
            shift_logits = logits[:, :-1, :].contiguous()
            shift_labels = labels[:, 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100
            )

        return {
            "loss": loss,
            "logits": logits,
            "scores": scores,
            "topk_indices": topk_indices,
            "original_tokens": N,
            "compressed_tokens": M,
            "compression_ratio": (1.0 - (M / N)) * 100.0,
            # Returned so a training log can PRINT which selection regime actually
            # ran. AGENTS.md's D5 and the merge_ratio=0.20 incident are both the same
            # failure: a knob that shaped a run while appearing nowhere in its own
            # artifact. `select_mode` decides what run 18 means, so it is reported by
            # the forward pass rather than transcribed from a config cell.
            "select_mode": select_mode
        }

    @torch.no_grad()
    def generate(
        self,
        pixel_values: torch.Tensor,
        decoder_input_ids: Optional[torch.Tensor] = None,
        decoder_start_token_id: Optional[int] = None,
        max_length: int = 512,
        keep_ratio: Optional[float] = None,
        merge_ratio: Optional[float] = None,
        select_mode: str = "router",
        **kwargs
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        k_ratio = keep_ratio if keep_ratio is not None else self.keep_ratio
        m_ratio = merge_ratio if merge_ratio is not None else self.merge_ratio

        B = pixel_values.shape[0]
        device = pixel_values.device

        # 1. Vision Encoder
        encoder_outputs = self.model.encoder(pixel_values)
        visual_tokens = encoder_outputs.last_hidden_state
        N = visual_tokens.shape[1]

        # 2. Coordinates & Saliency Filtering
        #    `select_mode` swaps the RANKING SIGNAL only; K, the architecture and the
        #    decoder are untouched, so rows are comparable at equal token budget. The
        #    per-mode documentation lives on `_selection_signal`, which both this path
        #    and the training path call -- see the note there on why it is shared.
        select_scores, invert = self._selection_signal(
            pixel_values, visual_tokens, select_mode)

        coords = self._generate_2d_coords(B, N, device, visual_tokens.dtype)
        selected_tokens, scores, topk_indices, pruned_coords = self.router(
            visual_tokens,
            keep_ratio=k_ratio,
            coords=coords,
            use_ste=False,
            select_scores=select_scores,
            invert=invert
        )
        
        # 3. ToMe Token Merging
        #    See forward(): the split is over ORIGINAL page position, so
        #    `topk_indices` must be threaded through. This matters more here than
        #    in training, because `select_mode` swaps the ranking signal and every
        #    mode reorders the sequence differently -- `random` most of all.
        tome_grid = self._token_grid(pixel_values, N) if m_ratio > 0.0 else None
        compressed_tokens, _ = self.tome_merger(
            selected_tokens,
            merge_ratio=m_ratio,
            coords=pruned_coords,
            orig_idx=topk_indices,
            token_grid=tome_grid
        )
        M = compressed_tokens.shape[1]
        
        # 4. Decoder Generation
        from transformers.modeling_outputs import BaseModelOutput
        custom_encoder_output = BaseModelOutput(last_hidden_state=compressed_tokens)
        
        gen_kwargs = dict(kwargs)
        if decoder_input_ids is not None:
            gen_kwargs["decoder_input_ids"] = decoder_input_ids
        elif decoder_start_token_id is not None:
            gen_kwargs["decoder_start_token_id"] = decoder_start_token_id
        else:
            gen_kwargs["decoder_start_token_id"] = getattr(self.model.config, "decoder_start_token_id", None) or 0

        # donut-base leaves eos/pad unset on the config; pass them explicitly so
        # generation can actually stop at </s> instead of running to max_length.
        gen_kwargs.setdefault("eos_token_id", 2)
        gen_kwargs.setdefault("pad_token_id", 1)

        # Decoding defaults measured by the Phase 2c ablation (50 FUNSD test docs,
        # control row reproduced the prior run to 0.00 pt). See AGENTS.md run 6 and
        # results/ablation_decoding.json.
        #
        # repetition_penalty must stay 1.0. At 1.3 it capped output at 71% of gold
        # length and cost 27.2 pts of word recall: the penalty divides the logit of
        # every token already emitted, but a full-page form legitimately re-uses its
        # whole vocabulary, so after ~80 words every plausible continuation is
        # downweighted while EOS -- never emitted -- is not. EOS wins and generation
        # stops mid-document. It also ate the repeated '"' in the JSON prefix, so
        # valid-JSON rate went 0% -> 82% when removed.
        #
        # no_repeat_ngram_size stays 3, and is the reason repetition collapse does
        # not return: with it removed the model over-generates to 124.6% of gold,
        # 22% of docs run to max_length, and recall drops 6.7 pts.
        gen_kwargs.setdefault("repetition_penalty", 1.0)
        gen_kwargs.setdefault("no_repeat_ngram_size", 3)

        generated_ids = self.model.generate(
            encoder_outputs=custom_encoder_output,
            max_length=max_length,
            **gen_kwargs
        )
        
        # Retained ink: what fraction of the page's contrast survived pruning. Logged
        # per call because it is the metric that explains an accuracy row -- D1 found
        # the router keeps 0.34-0.38 where random keeps 0.50, and without this number
        # a bad accuracy row looks like "pruning hurts" rather than "we pruned the text".
        retained_ink = None
        try:
            ink = patch_ink(pixel_values, N)
            total = ink.sum(dim=1)
            kept = ink.gather(1, topk_indices).sum(dim=1)
            retained_ink = float((kept / total.clamp(min=1e-9)).mean())
        except ValueError:
            pass  # non-standard grid; accuracy rows stay valid without this diagnostic

        meta = {
            "original_tokens": N,
            "compressed_tokens": M,
            "compression_ratio": (1.0 - (M / N)) * 100.0,
            "select_mode": select_mode,
            "retained_ink": retained_ink,
            "scores": scores,
            "topk_indices": topk_indices
        }
        return generated_ids, meta
