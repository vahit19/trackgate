import math


def wilson(k, n, z=1.96):
    """95% Wilson interval for a rate k/n."""
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def zero_upper(n, conf=0.95):
    """Upper bound on a rate when 0 of n observations failed (rule of three generalised)."""
    return 1 - (1 - conf) ** (1 / n) if n else 1.0


def quantile(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = (len(s) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)
