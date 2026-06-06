# GEATbx Examples: Parametric Optimization Benchmark Functions

Source PDF: `some_more_benchmarks.pdf`

Document metadata from the PDF:

- Title: `GEATbx_ Example Functions (single and m...e functions) 2 Parametric Optimization`
- Author: Piotr Blaszczyk
- Producer: Microsoft Print To PDF
- Creation date: 2026-06-06

Conversion notes:

- The local PDF has no extractable text layer. Its pages are composed of vector outlines and embedded images, so normal PDF text extraction returns empty pages.
- This Markdown version reconstructs the benchmark definitions into machine-readable Markdown and LaTeX.
- Function plots from the PDF are represented by figure captions only.
- Where the PDF/text source contains an apparent inconsistency, a short note is included instead of silently changing the content.

## Context

This document describes objective/test functions used with the Genetic and Evolutionary Algorithm Toolbox for Matlab (GEATbx). The functions in this Markdown file are the parametric optimization benchmark functions from Chapter 2 of the GEATbx example-functions document.

All implementations referenced below are Matlab objective-function files from GEATbx.

## Function Summary

| Section | Function | GEATbx implementation | Dimension | Search domain | Global minimum |
|---:|---|---|---|---|---|
| 2.1 | De Jong's function 1 / sphere model | `objfun1` | $n$ | $-5.12 \le x_i \le 5.12$ | $f(x)=0$ at $x_i=0$ |
| 2.2 | Axis parallel hyper-ellipsoid | `objfun1a` | $n$ | $-5.12 \le x_i \le 5.12$ | $f(x)=0$ at $x_i=0$ |
| 2.3 | Rotated hyper-ellipsoid / Schwefel 1.2 | `objfun1b` | $n$ | $-65.536 \le x_i \le 65.536$ | $f(x)=0$ at $x_i=0$ |
| 2.4 | Moved axis parallel hyper-ellipsoid | `objfun1c` | $n$ | $-5.12 \le x_i \le 5.12$ | Source states $f(x)=0$ at $x_i=5i$ |
| 2.5 | Rosenbrock's valley / De Jong's function 2 | `objfun2` | $n$ | $-2.048 \le x_i \le 2.048$ | $f(x)=0$ at $x_i=1$ |
| 2.6 | Rastrigin's function 6 | `objfun6` | $n$ | $-5.12 \le x_i \le 5.12$ | $f(x)=0$ at $x_i=0$ |
| 2.7 | Schwefel's function 7 | `objfun7` | $n$ | $-500 \le x_i \le 500$ | $f(x)=-418.9829n$ at $x_i=420.9687$ |
| 2.8 | Griewangk's function 8 | `objfun8` | $n$ | $-600 \le x_i \le 600$ | $f(x)=0$ at $x_i=0$ |
| 2.9 | Sum of different power function 9 | `objfun9` | $n$ | $-1 \le x_i \le 1$ | $f(x)=0$ at $x_i=0$ |
| 2.10 | Ackley's Path function 10 | `objfun10` | $n$ | $-32.768 \le x_i \le 32.768$ | $f(x)=0$ at $x_i=0$ |
| 2.11 | Langermann's function 11 | `objfun11` | variable | $0 \le x_i \le 10$ | Source states about $-1.4$ for $m=5$ |
| 2.12 | Michalewicz's function 12 | `objfun12` | $n$ | $0 \le x_i \le \pi$ | Source states $-4.687$ for $n=5$, $-9.66$ for $n=10$ |
| 2.13 | Branin's rcos function | `objbran` | 2 | $-5 \le x_1 \le 10$, $0 \le x_2 \le 15$ | $0.397887$ at three points |
| 2.14 | Easom's function | `objeaso` | 2 | $-100 \le x_i \le 100$ | $-1$ at $(\pi,\pi)$ |
| 2.15 | Goldstein-Price's function | `objgold` | 2 | $-2 \le x_i \le 2$ | $3$ at $(0,-1)$ |
| 2.16 | Six-hump camel back function | `objsixh` | 2 | $-3 \le x_1 \le 3$, $-2 \le x_2 \le 2$ | $-1.0316$ at two points |

## 2. Parametric Optimization

Each function in this chapter is described by its mathematical definition, variable domain, global minimum, implementation file, and figure captions.

## 2.1 De Jong's Function 1

Also known as the sphere model. It is continuous, convex, and unimodal.

### Definition

$$
f_1(x)=\sum_{i=1}^{n}x_i^2
$$

Domain:

$$
-5.12 \le x_i \le 5.12,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f1(x) = sum(x(i)^2), i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun1`

Figure caption:

- Fig. 2-1: Visualization of De Jong's function 1 using different variable domains. Both graphics look similar; only the scaling changes. Left: surf plot from -500 to 500 for both variables. Right: smaller area from -10 to 10.

## 2.2 Axis Parallel Hyper-Ellipsoid Function

Also known as the weighted sphere model. It is continuous, convex, and unimodal.

### Definition

$$
f_{1a}(x)=\sum_{i=1}^{n}i\,x_i^2
$$

Domain:

$$
-5.12 \le x_i \le 5.12,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f1a(x) = sum(i*x(i)^2), i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun1a`

Figure caption:

- Fig. 2-2: Visualization of the axis parallel hyper-ellipsoid function; surf/mesh plot in an area from -5 to 5.

## 2.3 Rotated Hyper-Ellipsoid Function

An extension of the axis parallel hyper-ellipsoid, also known as Schwefel's function 1.2. With respect to the coordinate axes, this function produces rotated hyper-ellipsoids. It is continuous, convex, and unimodal.

### Definition

$$
f_{1b}(x)=\sum_{i=1}^{n}\left(\sum_{j=1}^{i}x_j\right)^2
$$

Domain:

$$
-65.536 \le x_i \le 65.536,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f1b(x) = sum((sum(x(j), j = 1:i))^2), i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun1b`

Figure caption:

- Fig. 2-3: Visualization of the rotated hyper-ellipsoid function; surf/mesh plot of the first two variables in an area from -50 to 50.

## 2.4 Moved Axis Parallel Hyper-Ellipsoid Function

This function is derived from the axis parallel hyper-ellipsoid. The document states that the moved axis parallel hyper-ellipsoid function is more elliptic than the original function and that the minimum is not at $x_i=0$.

### Definition As Printed

The printed/text-extracted definition is:

$$
f_{1c}(x)=\sum_{i=1}^{n}5i\,x_i^2
$$

Domain:

$$
-5.12 \le x_i \le 5.12,\quad i=1,\ldots,n
$$

MATLAB-style definition as printed:

```matlab
f1c(x) = sum(5*i*x(i)^2), i = 1:n
```

Global minimum as printed:

$$
f(x)=0,\quad x_i=5i,\quad i=1,\ldots,n
$$

Implementation: `objfun1c`

### Consistency Note

The printed formula $\sum 5i\,x_i^2$ has its minimum at $x_i=0$, but the printed description and global-minimum statement say that the minimum is not at $0$ and occurs at $x_i=5i$. This appears inconsistent in the source. For faithful conversion, both the printed formula and the printed global-minimum statement are preserved here.

Figure caption:

- Fig. 2-4: Visualization of the moved axis parallel hyper-ellipsoid function; surf/mesh plot of the first and fourth variable. Objective values are calculated from the 4-dimensional function with the second and third variables set to 0.

## 2.5 Rosenbrock's Valley

Also known as De Jong's function 2 or the Banana function. The global optimum is inside a long, narrow, parabolic-shaped flat valley. Finding the valley is trivial, but convergence to the global optimum is difficult.

### Definition

$$
f_2(x)=\sum_{i=1}^{n-1}\left[100\left(x_{i+1}-x_i^2\right)^2+\left(1-x_i\right)^2\right]
$$

Domain:

$$
-2.048 \le x_i \le 2.048,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f2(x) = sum(100*(x(i+1)-x(i)^2)^2 + (1-x(i))^2), i = 1:n-1
```

Global minimum:

$$
f(x)=0,\quad x_i=1,\quad i=1,\ldots,n
$$

Implementation: `objfun2`

Figure caption:

- Fig. 2-5: Visualization of Rosenbrock's function. Left: full definition range. Right: focus around the global optimum at $[1,1]$.

## 2.6 Rastrigin's Function 6

Rastrigin's function is based on De Jong's function 1 with cosine modulation added to produce many local minima. The function is highly multimodal, but the local minima are regularly distributed.

### Definition

$$
f_6(x)=10n+\sum_{i=1}^{n}\left[x_i^2-10\cos(2\pi x_i)\right]
$$

Domain:

$$
-5.12 \le x_i \le 5.12,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f6(x) = 10*n + sum(x(i)^2 - 10*cos(2*pi*x(i))), i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun6`

Figure caption:

- Fig. 2-6: Visualization of Rastrigin's function. Left: surf plot from -5 to 5. Right: focus around the global optimum at $[0,0]$ in an area from -1 to 1.

## 2.7 Schwefel's Function 7

Schwefel's function is deceptive: the global minimum is geometrically distant from the next-best local minima. Search algorithms may converge in the wrong direction.

### Definition

$$
f_7(x)=\sum_{i=1}^{n}-x_i\sin\left(\sqrt{|x_i|}\right)
$$

Domain:

$$
-500 \le x_i \le 500,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f7(x) = sum(-x(i)*sin(sqrt(abs(x(i))))), i = 1:n
```

Global minimum:

$$
f(x)=-418.9829n,\quad x_i=420.9687,\quad i=1,\ldots,n
$$

Implementation: `objfun7`

Figure caption:

- Fig. 2-7: Visualization of Schwefel's function; surf plot in an area from -500 to 500.

## 2.8 Griewangk's Function 8

Griewangk's function is similar to Rastrigin's function. It has many widespread local minima, and their locations are regularly distributed.

### Definition

$$
f_8(x)=\sum_{i=1}^{n}\frac{x_i^2}{4000}
-\prod_{i=1}^{n}\cos\left(\frac{x_i}{\sqrt{i}}\right)+1
$$

Domain:

$$
-600 \le x_i \le 600,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f8(x) = sum(x(i)^2/4000) - prod(cos(x(i)/sqrt(i))) + 1, i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun8`

Figure captions and notes:

- Fig. 2-8: Visualization of Griewangk's function at three resolutions.
- Top left: full definition area from -500 to 500.
- Right: inner area from -50 to 50.
- Bottom left: area from -8 to 8 around the optimum at $[0,0]$.
- The full-range view resembles De Jong's function 1. In the inner area, many small peaks and valleys are visible. Near the optimum, the peaks and valleys look smooth.

## 2.9 Sum of Different Power Function 9

The sum of different powers is a commonly used unimodal test function.

### Definition

$$
f_9(x)=\sum_{i=1}^{n}|x_i|^{i+1}
$$

Domain:

$$
-1 \le x_i \le 1,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f9(x) = sum(abs(x(i))^(i+1)), i = 1:n
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun9`

Figure caption:

- Fig. 2-9: Visualization of the sum of different power function; surf plot in an area from -1 to 1.

## 2.10 Ackley's Path Function 10

Ackley's Path is a widely used multimodal test function.

### Definition

$$
f_{10}(x)=
-a\exp\left(-b\sqrt{\frac{1}{n}\sum_{i=1}^{n}x_i^2}\right)
-\exp\left(\frac{1}{n}\sum_{i=1}^{n}\cos(c x_i)\right)
+a+\exp(1)
$$

Parameters:

$$
a=20,\quad b=0.2,\quad c=2\pi
$$

Domain:

$$
-32.768 \le x_i \le 32.768,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f10(x) = -a*exp(-b*sqrt(1/n*sum(x(i)^2))) ...
         -exp(1/n*sum(cos(c*x(i)))) + a + exp(1)
```

Global minimum:

$$
f(x)=0,\quad x_i=0,\quad i=1,\ldots,n
$$

Implementation: `objfun10`

Figure caption:

- Fig. 2-10: Visualization of Ackley's Path function. Left: surf plot in an area from -30 to 30. Right: focus around the global optimum at $[0,0]$ in an area from -2 to 2.

## 2.11 Langermann's Function 11

The Langermann function is a multimodal test function. The local minima are unevenly distributed.

### Definition

Let $A_i$ be the $i$-th point/vector from the Langermann parameter matrix and $c_i$ the corresponding coefficient. The source refers readers to the Matlab file `objfun11` for the concrete values of $A$ and $c$.

$$
f_{11}(x)=
-\sum_{i=1}^{m}
c_i
\exp\left(
-\frac{1}{\pi}\sum_{j}(x_j-A_{ij})^2
\right)
\cos\left(
\pi\sum_{j}(x_j-A_{ij})^2
\right)
$$

Parameter/domain constraints:

$$
2 \le m \le 10,\quad 0 \le x_i \le 10
$$

MATLAB-style definition:

```matlab
f11(x) = -sum(c(i) * ...
              exp(-1/pi * sum((x - A(i))^2)) * ...
              cos(pi * sum((x - A(i))^2))), i = 1:m
```

Global minimum as printed:

$$
f(x)=-1.4\quad \text{for }m=5
$$

The minimizing $x_i$ values are not specified in the source and are shown as unknown.

Implementation: `objfun11`

Figure caption:

- Fig. 2-11: Visualization of Langermann's function. Left: surf plot in an area from 0 to 10 for the first and second variable. Right: same plot style for the second and third variable, with the first variable set to 0.

## 2.12 Michalewicz's Function 12

The Michalewicz function is multimodal and has $n!$ local optima. Parameter $m$ defines the steepness of valleys or edges. Larger $m$ makes the search more difficult; for very large $m$, the function behaves like a needle in a haystack.

### Definition

$$
f_{12}(x)=
-\sum_{i=1}^{n}
\sin(x_i)
\left[
\sin\left(\frac{i x_i^2}{\pi}\right)
\right]^{2m}
$$

Parameter:

$$
m=10
$$

Domain:

$$
0 \le x_i \le \pi,\quad i=1,\ldots,n
$$

MATLAB-style definition:

```matlab
f12(x) = -sum(sin(x(i)) * (sin(i*x(i)^2/pi))^(2*m)), i = 1:n, m = 10
```

Global minima as printed:

$$
f(x)=-4.687\quad \text{for }n=5
$$

$$
f(x)=-9.66\quad \text{for }n=10
$$

The minimizing $x_i$ values are not specified in the source and are shown as unknown.

Implementation: `objfun12`

Figure caption:

- Fig. 2-12: Visualization of Michalewicz's function. Top left: surf plot from 0 to 3 for the first and second variable. Right: area around the optimum. Bottom left: same as top left for the third and fourth variables, with variables 1 and 2 set to 0.

## 2.13 Branin's Rcos Function

The Branin rcos function is a 2-D global optimization test function with three global optima.

### Definition

$$
f_{\text{Bran}}(x_1,x_2)=
a\left(x_2-bx_1^2+cx_1-d\right)^2
+e(1-f)\cos(x_1)+e
$$

Parameters:

$$
a=1,\quad
b=\frac{5.1}{4\pi^2},\quad
c=\frac{5}{\pi},\quad
d=6,\quad
e=10,\quad
f=\frac{1}{8\pi}
$$

Domain:

$$
-5 \le x_1 \le 10,\quad 0 \le x_2 \le 15
$$

MATLAB-style definition:

```matlab
fBran(x1,x2) = a*(x2-b*x1^2+c*x1-d)^2 + e*(1-f)*cos(x1) + e
```

Global minima:

$$
f(x_1,x_2)=0.397887
$$

at:

$$
(x_1,x_2)=(-\pi,12.275),\quad (\pi,2.275),\quad (9.42478,2.475)
$$

Implementation: `objbran`

Figure caption:

- Fig. 2-13: Visualization of Branin's rcos function; surf plot of the definition range.

## 2.14 Easom's Function

The Easom function is a unimodal test function where the global minimum occupies a small area relative to the search space. The function is inverted for minimization.

### Definition

$$
f_{\text{Easo}}(x_1,x_2)=
-\cos(x_1)\cos(x_2)
\exp\left(-\left[(x_1-\pi)^2+(x_2-\pi)^2\right]\right)
$$

Domain:

$$
-100 \le x_i \le 100,\quad i=1,2
$$

MATLAB-style definition:

```matlab
fEaso(x1,x2) = -cos(x1)*cos(x2)*exp(-((x1-pi)^2+(x2-pi)^2))
```

Global minimum:

$$
f(x_1,x_2)=-1,\quad (x_1,x_2)=(\pi,\pi)
$$

Implementation: `objeaso`

Figure caption:

- Fig. 2-14: Visualization of Easom's function. Left: surf plot of a large area around the optimum/definition range. Right: direct area around the optimum.

## 2.15 Goldstein-Price's Function

The Goldstein-Price function is a 2-D global optimization test function.

### Definition

$$
\begin{aligned}
f_{\text{Gold}}(x_1,x_2)
=&
\left[
1+(x_1+x_2+1)^2
\left(
19-14x_1+3x_1^2-14x_2+6x_1x_2+3x_2^2
\right)
\right] \\
&\times
\left[
30+(2x_1-3x_2)^2
\left(
18-32x_1+12x_1^2+48x_2-36x_1x_2+27x_2^2
\right)
\right]
\end{aligned}
$$

Domain:

$$
-2 \le x_i \le 2,\quad i=1,2
$$

MATLAB-style definition:

```matlab
fGold(x1,x2) = ...
    (1+(x1+x2+1)^2*(19-14*x1+3*x1^2-14*x2+6*x1*x2+3*x2^2)) * ...
    (30+(2*x1-3*x2)^2*(18-32*x1+12*x1^2+48*x2-36*x1*x2+27*x2^2))
```

Global minimum:

$$
f(x_1,x_2)=3,\quad (x_1,x_2)=(0,-1)
$$

Implementation: `objgold`

Figure caption:

- Fig. 2-15: Visualization of Goldstein-Price's function; surf plot of the definition range.

## 2.16 Six-Hump Camel Back Function

The 2-D six-hump camel back function is a global optimization test function. Within the bounded region there are six local minima, two of which are global minima.

### Definition

$$
f_{\text{Sixh}}(x_1,x_2)=
\left(4-2.1x_1^2+\frac{x_1^4}{3}\right)x_1^2
+x_1x_2
+\left(-4+4x_2^2\right)x_2^2
$$

Domain:

$$
-3 \le x_1 \le 3,\quad -2 \le x_2 \le 2
$$

MATLAB-style definition:

```matlab
fSixh(x1,x2) = (4-2.1*x1^2+x1^4/3)*x1^2 + x1*x2 + (-4+4*x2^2)*x2^2
```

Global minima:

$$
f(x_1,x_2)=-1.0316
$$

at:

$$
(x_1,x_2)=(-0.0898,0.7126),\quad (0.0898,-0.7126)
$$

Implementation: `objsixh`

Figure caption:

- Fig. 2-16: Visualization of the six-hump camel back function. Left: surf plot of the area surrounding the minima. Right: smaller area around the minima.

## Index of Implementations

| Matlab file | Function |
|---|---|
| `objfun1` | De Jong's function 1 |
| `objfun1a` | Axis parallel hyper-ellipsoid |
| `objfun1b` | Rotated hyper-ellipsoid |
| `objfun1c` | Moved axis parallel hyper-ellipsoid |
| `objfun2` | Rosenbrock's valley |
| `objfun6` | Rastrigin's function 6 |
| `objfun7` | Schwefel's function 7 |
| `objfun8` | Griewangk's function 8 |
| `objfun9` | Sum of different power function 9 |
| `objfun10` | Ackley's Path function 10 |
| `objfun11` | Langermann's function 11 |
| `objfun12` | Michalewicz's function 12 |
| `objbran` | Branin's rcos function |
| `objeaso` | Easom's function |
| `objgold` | Goldstein-Price's function |
| `objsixh` | Six-hump camel back function |
