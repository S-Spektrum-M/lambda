# Paper Review: TurboQuant

[Read the article here](assets/papers/turboquant.pdf)

Vector quantization is one of those problems that sounds niche until you
realize it's sitting in the critical path of every LLM inference call you
make. Every token your model generates requires reading from a KV cache
that scales linearly with context length. Every nearest neighbor search
over a vector database requires comparing against millions of
high-dimensional embeddings. Compressing these vectors---quantizing
floating-point coordinates down to a few bits---is how you make any of
this tractable. The catch is that existing methods either need to see
your data ahead of time (offline quantization) or they fail to hit
optimal distortion rates for the bits they spend.

TurboQuant, from Zandieh et al. at Google Research and NYU, addresses
both problems. It's an online (data-oblivious) vector quantizer that
achieves near-optimal distortion bounds for both MSE and inner product
error, is fully vectorizable on accelerators, and requires zero
preprocessing. The paper backs this up with information-theoretic lower
bounds showing TurboQuant is within a $\approx 2.7\times$ constant factor of the best
any quantizer could possibly achieve.

## The Setup

The goal is to design a quantization map
$Q : \mathbb{R}^d \to \{0,1\}^B$ that compresses $d$-dimensional
vectors to $B = b \cdot d$ bits (i.e., $b$ bits per coordinate), along
with an inverse $Q^{-1} : \{0,1\}^B \to \mathbb{R}^d$ for
reconstruction. Two distortion measures matter:

$$D_{\text{mse}} := \mathbb{E}_Q\left[\|x - Q^{-1}(Q(x))\|_2^2\right]$$

$$D_{\text{prod}} := \mathbb{E}_Q\left[\left|\langle y, x \rangle - \langle y, Q^{-1}(Q(x)) \rangle\right|^2\right]$$

For inner product quantization, unbiasedness is additionally required:
$\mathbb{E}_Q\left[\langle y, Q^{-1}(Q(x)) \rangle\right] = \langle y, x \rangle$.
The quantizer is randomized and the expectations are over that
randomness. The input vectors are worst-case---no distributional
assumptions.

## The Core Idea

The insight is deceptively simple. Take your input vector, multiply it by
a random rotation matrix $\Pi \in \mathbb{R}^{d \times d}$, and observe
what happens to the coordinates. By Lemma 1, each coordinate of the
rotated vector $\Pi \cdot x$ (for $x \in \mathbb{S}^{d-1}$) follows a
scaled Beta distribution:

$$x_j \sim f_X(x) = \frac{\Gamma(d/2)}{\sqrt{\pi} \cdot \Gamma((d-1)/2)} \left(1 - x^2\right)^{(d-3)/2}$$

In high dimensions, this converges to $\mathcal{N}(0, 1/d)$. More
importantly, distinct coordinates become nearly independent---not just
uncorrelated, but actually independent in the limit. This means you can
treat vector quantization as a collection of independent scalar
quantization problems, one per coordinate.

For each coordinate, you solve the optimal scalar quantization problem:
partition $[-1, 1]$ into $2^b$ buckets by finding centroids
$c_1, \ldots, c_{2^b}$ that minimize the expected squared error under
$f_X$. This is a continuous 1D k-means problem:

$$\mathcal{C}(f_X, b) := \min_{-1 \leq c_1 \leq \cdots \leq c_{2^b} \leq 1} \sum_{i=1}^{2^b} \int_{\frac{c_{i-1}+c_i}{2}}^{\frac{c_i+c_{i+1}}{2}} |x - c_i|^2 \cdot f_X(x)\, dx$$

Solvable via Lloyd-Max. You precompute these codebooks once for each
bit-width, store them, and you're done.

The full TurboQuant$_{\text{mse}}$ procedure is:

1. Rotate the input: $y = \Pi \cdot x$
2. For each coordinate $j$, find the nearest centroid: $\text{idx}_j = \arg\min_{k \in [2^b]} |y_j - c_k|$
3. To dequantize: look up centroids $\tilde{y}_j = c_{\text{idx}_j}$, rotate back with $\tilde{x} = \Pi^\top \cdot \tilde{y}$

**Theorem 1** gives the MSE bound: for any $b \geq 1$ and any
$x \in \mathbb{S}^{d-1}$,

$$D_{\text{mse}} \leq \frac{\sqrt{3}\pi}{2} \cdot \frac{1}{4^b}$$

For small bit-widths $b = 1, 2, 3, 4$, the refined values are
$D_{\text{mse}} \approx 0.36, 0.117, 0.03, 0.009$.

In high dimensions where $f_X \to \mathcal{N}(0, 1/d)$, the optimal
centroids for $b = 1$ are $\left\{\pm\sqrt{2/\pi}/\sqrt{d}\right\}$ and
for $b = 2$ are
$\left\{\pm 0.453/\sqrt{d},\, \pm 1.51/\sqrt{d}\right\}$.

## The Bias Problem

Here's where it gets interesting. MSE-optimal quantizers are biased for
inner product estimation. If you quantize $x$ to minimize
reconstruction error and then compute inner products with the
reconstructed vector, you don't get an unbiased estimate of
$\langle y, x \rangle$.

The paper demonstrates this concretely for $b = 1$. At 1-bit, the
optimal MSE centroids are $\pm\sqrt{2/(\pi d)}$, and the quantization
map reduces to $Q_{\text{mse}}(x) = \text{sign}(\Pi \cdot x)$. The
dequantization is
$Q_{\text{mse}}^{-1}(z) = \sqrt{2/(\pi d)} \cdot \Pi^\top \cdot z$.
When you compute inner products through this, you pick up a
multiplicative bias of $2/\pi$:

$$\mathbb{E}\left[\langle y, Q_{\text{mse}}^{-1}(Q_{\text{mse}}(x)) \rangle\right] = \frac{2}{\pi} \cdot \langle y, x \rangle$$

This bias shrinks with increasing bit-width but it's always there.

## The Two-Stage Fix

TurboQuant$_{\text{prod}}$ solves the bias problem with an extra bit.
Given a budget of $b$ bits per coordinate:

1. Apply TurboQuant$_{\text{mse}}$ with bit-width $b - 1$
2. Compute the residual: $r = x - Q_{\text{mse}}^{-1}(Q_{\text{mse}}(x))$
3. Apply QJL to the residual: $\text{qjl} = \text{sign}(S \cdot r)$ where $S \in \mathbb{R}^{d \times d}$ has i.i.d. $\mathcal{N}(0,1)$ entries
4. Store the MSE indices, the QJL sign vector, and $\|r\|_2$

The QJL (Quantized Johnson-Lindenstrauss) transform from Zandieh et al.
2024 is defined as $Q_{\text{qjl}}(x) := \text{sign}(S \cdot x)$ with
dequantization
$Q_{\text{qjl}}^{-1}(z) := \frac{\sqrt{\pi/2}}{d} \cdot S^\top \cdot z$.
It's provably unbiased for inner products:
$\mathbb{E}\left[\langle y, Q_{\text{qjl}}^{-1}(Q_{\text{qjl}}(x)) \rangle\right] = \langle y, x \rangle$,
with variance bounded by
$\text{Var}\left(\langle y, Q_{\text{qjl}}^{-1}(Q_{\text{qjl}}(x)) \rangle\right) \leq \frac{\pi}{2d} \cdot \|y\|_2^2$.

The full inner product estimate becomes:

$$\langle y, Q_{\text{mse}}^{-1}(Q_{\text{mse}}(x)) \rangle + \|r\|_2 \cdot \langle y, Q_{\text{qjl}}^{-1}(Q_{\text{qjl}}(r)) \rangle$$

The proof of unbiasedness is clean: condition on the MSE reconstruction
$\tilde{x}_{\text{mse}}$, use QJL's unbiasedness to get
$\mathbb{E}[\langle y, \tilde{x}_{\text{qjl}} \rangle | \tilde{x}_{\text{mse}}] = \langle y, r \rangle$,
then by linearity
$\mathbb{E}[\langle y, \tilde{x} \rangle | \tilde{x}_{\text{mse}}] = \langle y, \tilde{x}_{\text{mse}} \rangle + \langle y, r \rangle = \langle y, x \rangle$.
Tower property gives unconditional unbiasedness.

**Theorem 2** gives the inner product distortion bound:

$$D_{\text{prod}} \leq \frac{\sqrt{3}\pi^2 \cdot \|y\|_2^2}{d} \cdot \frac{1}{4^b}$$

For $b = 1, 2, 3, 4$:
$D_{\text{prod}} \approx \frac{1.57}{d},\, \frac{0.56}{d},\, \frac{0.18}{d},\, \frac{0.047}{d}$.

## Lower Bounds

The paper proves matching (up to constants) lower bounds via Shannon's
source coding theorem and Yao's minimax principle. The Shannon Lower
Bound for a random vector $x \in \mathbb{S}^{d-1}$ (uniform on the
hypersphere) with total bit complexity $B$ gives:

$$D(B) \geq 2^{-2B/d}$$

Combined with Yao's minimax---which equates worst-case randomized
distortion to average-case deterministic distortion---this yields
**Theorem 3**: for any randomized quantizer $Q$ with bit-width $b$,
there exist hard instances $x, y \in \mathbb{S}^{d-1}$ such that:

$$D_{\text{mse}}(Q) \geq \frac{1}{4^b}, \qquad D_{\text{prod}}(Q) \geq \frac{1}{d} \cdot \frac{1}{4^b}$$

TurboQuant's upper bounds differ from these by $\frac{\sqrt{3}\pi}{2} \approx 2.7\times$ for MSE.
At $b = 1$, TurboQuant is within $1.45\times$ of optimal---confirmed empirically.

## Experiments

The experimental results are strong across three domains.

**KV Cache Quantization.** On the Needle-in-a-Haystack benchmark with
Llama-3.1-8B-Instruct, TurboQuant at $4\times$ compression (2.5 bits
effective) matches full-precision recall exactly (0.997 vs 0.997).
Methods like SnapKV (0.858) and PyramidKV (0.895) that lack formal
guarantees degrade noticeably. On LongBench-V1, TurboQuant at 3.5 bits
per channel matches full-cache performance (50.06 vs 50.06 average)
while compressing by $4.5\times$. It also quantizes during generation,
unlike PolarQuant and KIVI which leave generated tokens unquantized.

**Nearest Neighbor Search.** TurboQuant consistently outperforms Product
Quantization and RabitQ on recall@k across GloVe ($d = 200$), OpenAI3
($d = 1536$), and OpenAI3 ($d = 3072$) embeddings, at both 2-bit and
4-bit quantization. The real kicker is indexing time: TurboQuant
quantizes 100k vectors in 0.0007--0.0021 seconds versus PQ's 37--494
seconds and RabitQ's 597--3957 seconds. That's 5--6 orders of magnitude
faster. The algorithm is data-oblivious, so there's no codebook to
learn.

**Empirical Validation.** The observed distortion curves on the DBpedia
dataset closely track the theoretical upper ($\frac{\sqrt{3}\pi}{2} \cdot 4^{-b}$)
and lower ($4^{-b}$) bounds, confirming the analysis isn't just loose
asymptotic hand-waving.

## What I Like

The random rotation trick is the kind of idea that seems obvious in
retrospect but required real insight to formalize. The fact that
$\Pi \cdot x$ induces near-independence (not just decorrelation) across
coordinates is what makes the whole scalar quantization reduction work
with provable guarantees. Most "rotate then quantize" schemes (QuIP,
QuaRot) are offline and data-dependent; TurboQuant is neither.

The two-stage approach for inner products is also well-motivated. Rather
than trying to design a single quantizer that simultaneously minimizes
$D_{\text{mse}}$ and provides unbiased inner products---objectives that
fundamentally conflict---they decompose the problem: spend $b - 1$ bits
on MSE-optimal quantization, spend 1 bit on debiasing the residual via
QJL. The information budget is cleanly allocated.

The quantization speed advantage is massive and underappreciated. For
online applications like KV cache compression where you're quantizing
every new token's key/value vectors during generation, the computational
cost of quantization is on the critical path. TurboQuant's operations
(matrix-vector multiply, nearest centroid lookup from a precomputed
table) are exactly the kind of thing accelerators are designed to do
fast.

## What I'd Push On

The $\approx 2.7\times$ gap to the lower bound for MSE is a constant,
but it's not tight. The paper acknowledges this but doesn't investigate
whether the lower bound or the upper bound (or both) can be improved.
For inner products the gap is larger
($\sqrt{3}\pi^2 \approx 17\times$, though tighter at low bit-widths). Is
this inherent to the two-stage approach, or is there a tighter analysis?

The random rotation matrix $\Pi$ is $d \times d$, which is $O(d^2)$
storage. For large $d$ (e.g., $d = 3072$ for OpenAI embeddings), this is
36MB in float32. The paper uses QR decomposition of a random Gaussian
matrix to generate $\Pi$, which is $O(d^3)$ compute. For truly online
settings where you might want different rotations for different data
partitions, this could become a bottleneck. Structured random rotations
(randomized Hadamard, etc.) could reduce this to $O(d \log d)$ but might
affect the independence guarantees.

The LongBench results at 2.5 bits (49.44 average) show a small but real
quality drop compared to full cache (50.06). The paper's outlier channel
treatment---splitting channels into outlier and non-outlier groups with
different bit-widths---is borrowed from prior work and feels somewhat ad
hoc relative to the paper's otherwise clean theoretical framework. A
principled approach to non-uniform bit allocation across channels would
strengthen the story.

## Bottom Line

TurboQuant is a clean contribution: a theoretically grounded, practically
fast, data-oblivious vector quantizer with provably near-optimal
distortion. The combination of random rotation + optimal scalar
quantization + QJL residual correction is simple enough to implement in a
few hundred lines of code, runs at accelerator speed, and comes with
matching lower bounds. For anyone building KV cache compression or vector
search at scale, this is worth reading.
