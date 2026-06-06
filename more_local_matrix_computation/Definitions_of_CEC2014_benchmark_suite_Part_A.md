# Problem Definitions and Evaluation Criteria for the CEC 2014 Special Session and Competition on Single Objective Real-Parameter Numerical Optimization

Authors:

- J. J. Liang, School of Electrical Engineering, Zhengzhou University, Zhengzhou, China
- B. Y. Qu, School of Electric and Information Engineering, Zhongyuan University of Technology, Zhengzhou, China
- P. N. Suganthan, School of EEE, Nanyang Technological University, Singapore

Emails: `liangjing@zzu.edu.cn`, `qby1984@hotmail.com`, `epnsugan@ntu.edu.sg`

Technical Report 201311, Computational Intelligence Laboratory, Zhengzhou University, Zhengzhou, China, and Technical Report, Nanyang Technological University, Singapore.

Date: December 2013

Source PDF: `Definitions of  CEC2014 benchmark suite Part A.pdf`

Conversion notes:

- This Markdown version rewrites the PDF's mathematical formulas in LaTeX for machine readability.
- Figure images from the PDF are represented by their captions only.
- The source PDF states that the benchmark problems should be treated as black-box problems; explicit equations should not be used by competition participants.

## 1. Introduction to the CEC 2014 Benchmark Suite

Research on single objective optimization algorithms is the basis of research on more complex optimization algorithms such as multi-objective optimization algorithms, niching algorithms, constrained optimization algorithms, and so on. All new evolutionary and swarm algorithms are tested on single objective benchmark problems. In addition, these single objective benchmark problems can be transformed into dynamic, niching, composition, computationally expensive, and many other classes of problems.

In recent years, various novel optimization algorithms have been proposed to solve real-parameter optimization problems, including the CEC 2005 and CEC 2013 special sessions on real-parameter optimization. Considering the comments on the CEC 2013 test suite, this competition uses a new test suite for real-parameter single objective optimization.

The benchmark problems include novel basic problems, composition test problems built by extracting features dimension-wise from several problems, graded levels of linkages, rotated trap problems, and related features. This competition excludes the usage of surrogates or meta-models. A sub-competition tests algorithms with a very small number of function evaluations to emulate computationally expensive optimization; that sub-competition encourages surrogate and approximation approaches.

The C and Matlab codes for the CEC 2014 test suite were published at:

```text
http://www.ntu.edu.sg/home/EPNSugan/index_files/CEC2014
```

## 1.1 Definitions

All test functions are minimization problems:

$$
\min f(x), \quad x=[x_1,x_2,\ldots,x_D]^T
$$

Where:

- $D$ is the number of dimensions.
- $o_i=[o_{i1},o_{i2},\ldots,o_{iD}]^T$ is the shifted global optimum, defined in `shift_data_x.txt`, randomly distributed in $[-80,80]^D$.
- Each CEC 2014 function has its own shift data.
- All test functions are shifted to $o_i$ and are scalable.
- The search range is the same for all functions: $[-100,100]^D$.
- $M_i$ is the rotation matrix. Different from CEC 2013, a different rotation matrix is assigned to each function and each basic function.

For real-world problems, it is uncommon for linkages to exist among all variables. In CEC 2014, variables are divided randomly into subcomponents. The rotation matrix for each subcomponent is generated from standard normally distributed entries by Gram-Schmidt orthonormalization with condition number $c$ equal to 1 or 2.

## 1.2 Summary of the CEC 2014 Test Suite

Search range for all functions: $[-100,100]^D$.

| Class | No. | Function | $F_i^*=F_i(x^*)$ |
|---|---:|---|---:|
| Unimodal | 1 | Rotated High Conditioned Elliptic Function | 100 |
| Unimodal | 2 | Rotated Bent Cigar Function | 200 |
| Unimodal | 3 | Rotated Discus Function | 300 |
| Simple Multimodal | 4 | Shifted and Rotated Rosenbrock's Function | 400 |
| Simple Multimodal | 5 | Shifted and Rotated Ackley's Function | 500 |
| Simple Multimodal | 6 | Shifted and Rotated Weierstrass Function | 600 |
| Simple Multimodal | 7 | Shifted and Rotated Griewank's Function | 700 |
| Simple Multimodal | 8 | Shifted Rastrigin's Function | 800 |
| Simple Multimodal | 9 | Shifted and Rotated Rastrigin's Function | 900 |
| Simple Multimodal | 10 | Shifted Schwefel's Function | 1000 |
| Simple Multimodal | 11 | Shifted and Rotated Schwefel's Function | 1100 |
| Simple Multimodal | 12 | Shifted and Rotated Katsuura Function | 1200 |
| Simple Multimodal | 13 | Shifted and Rotated HappyCat Function | 1300 |
| Simple Multimodal | 14 | Shifted and Rotated HGBat Function | 1400 |
| Simple Multimodal | 15 | Shifted and Rotated Expanded Griewank's plus Rosenbrock's Function | 1500 |
| Simple Multimodal | 16 | Shifted and Rotated Expanded Scaffer's F6 Function | 1600 |
| Hybrid | 17 | Hybrid Function 1 ($N=3$) | 1700 |
| Hybrid | 18 | Hybrid Function 2 ($N=3$) | 1800 |
| Hybrid | 19 | Hybrid Function 3 ($N=4$) | 1900 |
| Hybrid | 20 | Hybrid Function 4 ($N=4$) | 2000 |
| Hybrid | 21 | Hybrid Function 5 ($N=5$) | 2100 |
| Hybrid | 22 | Hybrid Function 6 ($N=5$) | 2200 |
| Composition | 23 | Composition Function 1 ($N=5$) | 2300 |
| Composition | 24 | Composition Function 2 ($N=3$) | 2400 |
| Composition | 25 | Composition Function 3 ($N=3$) | 2500 |
| Composition | 26 | Composition Function 4 ($N=5$) | 2600 |
| Composition | 27 | Composition Function 5 ($N=5$) | 2700 |
| Composition | 28 | Composition Function 6 ($N=5$) | 2800 |
| Composition | 29 | Composition Function 7 ($N=3$) | 2900 |
| Composition | 30 | Composition Function 8 ($N=3$) | 3000 |

Note from the PDF: these problems should be treated as black-box problems. The explicit equations of the problems are not to be used.

## 1.3 Basic Function Definitions

The following functions are the basic components used to build the benchmark suite.

### 1. High Conditioned Elliptic Function

$$
f_1(x)=\sum_{i=1}^{D} (10^6)^{\frac{i-1}{D-1}} x_i^2
\tag{1}
$$

### 2. Bent Cigar Function

$$
f_2(x)=x_1^2+10^6\sum_{i=2}^{D} x_i^2
\tag{2}
$$

### 3. Discus Function

$$
f_3(x)=10^6x_1^2+\sum_{i=2}^{D}x_i^2
\tag{3}
$$

### 4. Rosenbrock's Function

$$
f_4(x)=\sum_{i=1}^{D-1}\left[100(x_i^2-x_{i+1})^2+(x_i-1)^2\right]
\tag{4}
$$

### 5. Ackley's Function

$$
f_5(x)=-20\exp\left(-0.2\sqrt{\frac{1}{D}\sum_{i=1}^{D}x_i^2}\right)
-\exp\left(\frac{1}{D}\sum_{i=1}^{D}\cos(2\pi x_i)\right)+20+e
\tag{5}
$$

### 6. Weierstrass Function

$$
f_6(x)=
\sum_{i=1}^{D}\left[\sum_{k=0}^{k_{\max}}a^k\cos\left(2\pi b^k(x_i+0.5)\right)\right]
-D\sum_{k=0}^{k_{\max}}a^k\cos\left(2\pi b^k\cdot0.5\right)
\tag{6}
$$

Parameters:

$$
a=0.5,\quad b=3,\quad k_{\max}=20
$$

### 7. Griewank's Function

$$
f_7(x)=1+\frac{1}{4000}\sum_{i=1}^{D}x_i^2-\prod_{i=1}^{D}\cos\left(\frac{x_i}{\sqrt{i}}\right)
\tag{7}
$$

### 8. Rastrigin's Function

$$
f_8(x)=\sum_{i=1}^{D}\left[x_i^2-10\cos(2\pi x_i)+10\right]
\tag{8}
$$

### 9. Modified Schwefel's Function

$$
f_9(x)=418.9829D-\sum_{i=1}^{D}g(z_i)
\tag{9}
$$

with:

$$
z_i=x_i+4.209687462275036e+002
$$

and:

$$
g(z_i)=
\begin{cases}
z_i\sin\left(\sqrt{|z_i|}\right), & |z_i|\le 500,\\
\left(500-\operatorname{mod}(z_i,500)\right)
\sin\left(\sqrt{\left|500-\operatorname{mod}(z_i,500)\right|}\right)
-\dfrac{(z_i-500)^2}{10000D}, & z_i>500,\\
\left(\operatorname{mod}(|z_i|,500)-500\right)
\sin\left(\sqrt{\left|\operatorname{mod}(|z_i|,500)-500\right|}\right)
-\dfrac{(z_i+500)^2}{10000D}, & z_i<-500.
\end{cases}
$$

### 10. Katsuura Function

$$
f_{10}(x)=
\frac{10}{D^2}
\prod_{i=1}^{D}
\left(
1+i\sum_{j=1}^{32}
\frac{\left|2^jx_i-\operatorname{round}(2^jx_i)\right|}{2^j}
\right)^{\frac{10}{D^{1.2}}}
-\frac{10}{D^2}
\tag{10}
$$

### 11. HappyCat Function

$$
f_{11}(x)=
\left|\sum_{i=1}^{D}x_i^2-D\right|^{1/4}
+\frac{0.5\sum_{i=1}^{D}x_i^2+\sum_{i=1}^{D}x_i}{D}
+0.5
\tag{11}
$$

### 12. HGBat Function

$$
f_{12}(x)=
\left|
\left(\sum_{i=1}^{D}x_i^2\right)^2
-\left(\sum_{i=1}^{D}x_i\right)^2
\right|^{1/2}
+\frac{0.5\sum_{i=1}^{D}x_i^2+\sum_{i=1}^{D}x_i}{D}
+0.5
\tag{12}
$$

### 13. Expanded Griewank's plus Rosenbrock's Function

$$
f_{13}(x)=
f_7(f_4(x_1,x_2))
+f_7(f_4(x_2,x_3))
+\cdots
+f_7(f_4(x_{D-1},x_D))
+f_7(f_4(x_D,x_1))
\tag{13}
$$

Here $f_4(x_i,x_{i+1})$ denotes the two-variable Rosenbrock term:

$$
f_4(x_i,x_{i+1})=100(x_i^2-x_{i+1})^2+(x_i-1)^2
$$

and the one-dimensional Griewank transform is:

$$
f_7(y)=\frac{y^2}{4000}-\cos(y)+1
$$

### 14. Expanded Scaffer's F6 Function

Scaffer's F6 pair function:

$$
g(x,y)=0.5+
\frac{\sin^2\left(\sqrt{x^2+y^2}\right)-0.5}
{\left(1+0.001(x^2+y^2)\right)^2}
$$

Expanded function:

$$
f_{14}(x)=
g(x_1,x_2)+g(x_2,x_3)+\cdots+g(x_{D-1},x_D)+g(x_D,x_1)
\tag{14}
$$

## 1.4 Definitions of the CEC 2014 Test Suite

### A. Unimodal Functions

### 1. Rotated High Conditioned Elliptic Function

$$
F_1(x)=f_1(M_1(x-o_1))+F_1^*
\tag{15}
$$

Figure caption: Figure 1. 3-D map for 2-D function.

Properties:

- Unimodal
- Non-separable
- Quadratic ill-conditioned

### 2. Rotated Bent Cigar Function

$$
F_2(x)=f_2(M_2(x-o_2))+F_2^*
\tag{16}
$$

Figure caption: Figure 2. 3-D map for 2-D function.

Properties:

- Unimodal
- Non-separable
- Smooth but narrow ridge

### 3. Rotated Discus Function

$$
F_3(x)=f_3(M_3(x-o_3))+F_3^*
\tag{17}
$$

Figure caption: Figure 3. 3-D map for 2-D function.

Properties:

- Unimodal
- Non-separable
- With one sensitive direction

### B. Multimodal Functions

### 4. Shifted and Rotated Rosenbrock's Function

$$
F_4(x)=f_4\left(M_4\left(\frac{2.048(x-o_4)}{100}\right)+\mathbf{1}\right)+F_4^*
\tag{18}
$$

Figure captions:

- Figure 4(a). 3-D map for 2-D function.
- Figure 4(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Having a very narrow valley from local optimum to global optimum

### 5. Shifted and Rotated Ackley's Function

$$
F_5(x)=f_5(M_5(x-o_5))+F_5^*
\tag{19}
$$

Figure caption: Figure 5. 3-D map for 2-D function.

Properties:

- Multi-modal
- Non-separable

### 6. Shifted and Rotated Weierstrass Function

$$
F_6(x)=f_6\left(M_6\left(\frac{0.5(x-o_6)}{100}\right)\right)+F_6^*
\tag{20}
$$

Figure caption: Figure 6. 3-D map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Continuous but differentiable only on a set of points

### 7. Shifted and Rotated Griewank's Function

$$
F_7(x)=f_7\left(M_7\left(\frac{600(x-o_7)}{100}\right)\right)+F_7^*
\tag{21}
$$

Figure captions:

- Figure 7(a). 3-D map for 2-D function.
- Figure 7(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Rotated
- Non-separable

### 8. Shifted Rastrigin's Function

$$
F_8(x)=f_8\left(\frac{5.12(x-o_8)}{100}\right)+F_8^*
\tag{22}
$$

Figure caption: Figure 8. 3-D map for 2-D function.

Properties:

- Multi-modal
- Separable
- Local optima's number is huge

### 9. Shifted and Rotated Rastrigin's Function

$$
F_9(x)=f_8\left(M_9\left(\frac{5.12(x-o_9)}{100}\right)\right)+F_9^*
\tag{23}
$$

Figure caption: Figure 9. 3-D map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Local optima's number is huge

### 10. Shifted Schwefel's Function

$$
F_{10}(x)=f_9\left(\frac{1000(x-o_{10})}{100}\right)+F_{10}^*
\tag{24}
$$

Figure captions:

- Figure 10(a). 3-D map for 2-D function.
- Figure 10(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Separable
- Local optima's number is huge and second better local optimum is far from the global optimum.

### 11. Shifted and Rotated Schwefel's Function

$$
F_{11}(x)=f_9\left(M_{11}\left(\frac{1000(x-o_{11})}{100}\right)\right)+F_{11}^*
\tag{25}
$$

Figure captions:

- Figure 11(a). 3-D map for 2-D function.
- Figure 11(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Local optima's number is huge and second better local optimum is far from the global optimum.

### 12. Shifted and Rotated Katsuura Function

$$
F_{12}(x)=f_{10}\left(M_{12}\left(\frac{5(x-o_{12})}{100}\right)\right)+F_{12}^*
\tag{26}
$$

Figure captions:

- Figure 12(a). 3-D map for 2-D function.
- Figure 12(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Continuous everywhere yet differentiable nowhere

### 13. Shifted and Rotated HappyCat Function

$$
F_{13}(x)=f_{11}\left(M_{13}\left(\frac{5(x-o_{13})}{100}\right)\right)+F_{13}^*
\tag{27}
$$

Figure captions:

- Figure 13(a). 3-D map for 2-D function.
- Figure 13(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable

### 14. Shifted and Rotated HGBat Function

$$
F_{14}(x)=f_{12}\left(M_{14}\left(\frac{5(x-o_{14})}{100}\right)\right)+F_{14}^*
\tag{28}
$$

Figure captions:

- Figure 14(a). 3-D map for 2-D function.
- Figure 14(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable

### 15. Shifted and Rotated Expanded Griewank's plus Rosenbrock's Function

$$
F_{15}(x)=f_{13}\left(M_{15}\left(\frac{5(x-o_{15})}{100}\right)+\mathbf{1}\right)+F_{15}^*
\tag{29}
$$

Figure captions:

- Figure 15(a). 3-D map for 2-D function.
- Figure 15(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable

### 16. Shifted and Rotated Expanded Scaffer's F6 Function

$$
F_{16}(x)=f_{14}(M_{16}(x-o_{16})+\mathbf{1})+F_{16}^*
\tag{30}
$$

Figure caption: Figure 16. 3-D map for 2-D function.

Properties:

- Multi-modal
- Non-separable

### C. Hybrid Functions

In real-world optimization problems, different subcomponents of the variables may have different properties. In this set of hybrid functions, variables are randomly divided into subcomponents and different basic functions are used for different subcomponents.

General hybrid function:

$$
F(x)=g_1(M_1z_1)+g_2(M_2z_2)+\cdots+g_N(M_Nz_N)+F^*
\tag{31}
$$

Where:

- $F(x)$ is the hybrid function.
- $g_i(x)$ is the $i$-th basic function used to construct the hybrid function.
- $N$ is the number of basic functions.
- $z=[z_1,z_2,\ldots,z_N]$.
- $y=x-o_i$.
- $S=\operatorname{randperm}(1:D)$ is a random permutation of the dimensions.
- $p_i$ controls the percentage of $g_i(x)$.
- $n_i$ is the dimension assigned to each basic function.

Subcomponent split:

$$
z_1=[y_{S_1},y_{S_2},\ldots,y_{S_{n_1}}]
$$

$$
z_2=[y_{S_{n_1+1}},y_{S_{n_1+2}},\ldots,y_{S_{n_1+n_2}}]
$$

$$
z_N=[y_{S_{\sum_{i=1}^{N-1}n_i+1}},\ldots,y_{S_D}]
$$

Dimension allocation:

$$
\sum_{i=1}^{N}n_i=D
$$

$$
n_1=\lceil p_1D\rceil,\quad
n_2=\lceil p_2D\rceil,\quad
\ldots,\quad
n_{N-1}=\lceil p_{N-1}D\rceil,\quad
n_N=D-\sum_{i=1}^{N-1}n_i
$$

Properties of hybrid functions:

- Multi-modal or unimodal, depending on the basic functions.
- Non-separable subcomponents.
- Different properties for different variable subcomponents.

### 17. Hybrid Function 1

Parameters:

- $N=3$
- $p=[0.3,0.3,0.4]$
- $F_{17}^*=1700$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | Modified Schwefel's Function $f_9$ |
| $g_2$ | Rastrigin's Function $f_8$ |
| $g_3$ | High Conditioned Elliptic Function $f_1$ |

### 18. Hybrid Function 2

Parameters:

- $N=3$
- $p=[0.3,0.3,0.4]$
- $F_{18}^*=1800$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | Bent Cigar Function $f_2$ |
| $g_2$ | HGBat Function $f_{12}$ |
| $g_3$ | Rastrigin's Function $f_8$ |

### 19. Hybrid Function 3

Parameters:

- $N=4$
- $p=[0.2,0.2,0.3,0.3]$
- $F_{19}^*=1900$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | Griewank's Function $f_7$ |
| $g_2$ | Weierstrass Function $f_6$ |
| $g_3$ | Rosenbrock's Function $f_4$ |
| $g_4$ | Scaffer's F6 Function $f_{14}$ |

### 20. Hybrid Function 4

Parameters:

- $N=4$
- $p=[0.2,0.2,0.3,0.3]$
- $F_{20}^*=2000$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | HGBat Function $f_{12}$ |
| $g_2$ | Discus Function $f_3$ |
| $g_3$ | Expanded Griewank's plus Rosenbrock's Function $f_{13}$ |
| $g_4$ | Rastrigin's Function $f_8$ |

### 21. Hybrid Function 5

Parameters:

- $N=5$
- $p=[0.1,0.2,0.2,0.2,0.3]$
- $F_{21}^*=2100$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | Scaffer's F6 Function $f_{14}$ |
| $g_2$ | HGBat Function $f_{12}$ |
| $g_3$ | Rosenbrock's Function $f_4$ |
| $g_4$ | Modified Schwefel's Function $f_9$ |
| $g_5$ | High Conditioned Elliptic Function $f_1$ |

### 22. Hybrid Function 6

Parameters:

- $N=5$
- $p=[0.1,0.2,0.2,0.2,0.3]$
- $F_{22}^*=2200$

Components:

| Component | Basic function |
|---|---|
| $g_1$ | Katsuura Function $f_{10}$ |
| $g_2$ | HappyCat Function $f_{11}$ |
| $g_3$ | Expanded Griewank's plus Rosenbrock's Function $f_{13}$ |
| $g_4$ | Modified Schwefel's Function $f_9$ |
| $g_5$ | Ackley's Function $f_5$ |

### D. Composition Functions

General composition function:

$$
F(x)=\sum_{i=1}^{N}\omega_i\left[\lambda_i g_i(x)+bias_i\right]+F^*
\tag{32}
$$

Where:

- $F(x)$ is the composition function.
- $g_i(x)$ is the $i$-th basic function used to construct the composition function.
- $N$ is the number of basic functions.
- $o_i$ is the new shifted optimum position for each $g_i(x)$ and defines the global and local optima positions.
- $bias_i$ defines which optimum is the global optimum.
- $\sigma_i$ controls each $g_i(x)$ coverage range. A small $\sigma_i$ gives a narrow range for that $g_i(x)$.
- $\lambda_i$ controls each $g_i(x)$ height.
- $\omega_i$ is the normalized weight value for each $g_i(x)$.

Unnormalized weight:

$$
w_i=
\frac{1}{\sqrt{\sum_{j=1}^{D}(x_j-o_{ij})^2}}
\exp\left(
-\frac{\sum_{j=1}^{D}(x_j-o_{ij})^2}{2D\sigma_i^2}
\right)
\tag{33}
$$

Normalized weight:

$$
\omega_i=\frac{w_i}{\sum_{i=1}^{N}w_i}
$$

When $x=o_i$:

$$
\omega_j=
\begin{cases}
1, & j=i,\\
0, & j\ne i.
\end{cases}
$$

At $x=o_i$:

$$
F(x)=bias_i+F^*
$$

The local optimum with the smallest bias value is the global optimum. The composition function merges the properties of the subfunctions and maintains continuity around the global and local optima.

Functions $F_i'=F_i-F_i^*$ are used as $g_i$. In this way, the function values of the global optima of all $g_i$ are equal to 0 for all composition functions in this report.

In CEC 2014, hybrid functions are also used as the basic functions for Composition Function 7 and Composition Function 8. With hybrid functions as basic functions, a composition function can have different properties for different variable subcomponents.

Note from the PDF: to test algorithms' tendency to converge to the search center, a local optimum is set to the origin as a trap for each composition function included in this benchmark suite.

### 23. Composition Function 1

Parameters:

- $N=5$
- $\sigma=[10,20,30,40,50]$
- $\lambda=[1,1e-6,1e-26,1e-6,1e-6]$
- $bias=[0,100,200,300,400]$
- $F_{23}^*=2300$

Components:

| Component | Function |
|---|---|
| $g_1$ | Rotated Rosenbrock's Function $F_4'$ |
| $g_2$ | High Conditioned Elliptic Function $F_1'$ |
| $g_3$ | Rotated Bent Cigar Function $F_2'$ |
| $g_4$ | Rotated Discus Function $F_3'$ |
| $g_5$ | High Conditioned Elliptic Function $F_1'$ |

Figure captions:

- Figure 17(a). 3-D map for 2-D function.
- Figure 17(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima

### 24. Composition Function 2

Parameters:

- $N=3$
- $\sigma=[20,20,20]$
- $\lambda=[1,1,1]$
- $bias=[0,100,200]$
- $F_{24}^*=2400$

Components:

| Component | Function |
|---|---|
| $g_1$ | Schwefel's Function $F_{10}'$ |
| $g_2$ | Rotated Rastrigin's Function $F_9'$ |
| $g_3$ | Rotated HGBat Function $F_{14}'$ |

Figure captions:

- Figure 18(a). 3-D map for 2-D function.
- Figure 18(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Different properties around different local optima

### 25. Composition Function 3

Parameters:

- $N=3$
- $\sigma=[10,30,50]$
- $\lambda=[0.25,1,1e-7]$
- $bias=[0,100,200]$
- $F_{25}^*=2500$

Components:

| Component | Function |
|---|---|
| $g_1$ | Rotated Schwefel's Function $F_{11}'$ |
| $g_2$ | Rotated Rastrigin's Function $F_9'$ |
| $g_3$ | Rotated High Conditioned Elliptic Function $F_1'$ |

Figure captions:

- Figure 19(a). 3-D map for 2-D function.
- Figure 19(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima

### 26. Composition Function 4

Parameters:

- $N=5$
- $\sigma=[10,10,10,10,10]$
- $\lambda=[0.25,1,1e-7,2.5,10]$
- $bias=[0,100,200,300,400]$
- $F_{26}^*=2600$

Components:

| Component | Function |
|---|---|
| $g_1$ | Rotated Schwefel's Function $F_{11}'$ |
| $g_2$ | Rotated HappyCat Function $F_{13}'$ |
| $g_3$ | Rotated High Conditioned Elliptic Function $F_1'$ |
| $g_4$ | Rotated Weierstrass Function $F_6'$ |
| $g_5$ | Rotated Griewank's Function $F_7'$ |

Figure captions:

- Figure 20(a). 3-D map for 2-D function.
- Figure 20(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima

### 27. Composition Function 5

Parameters:

- $N=5$
- $\sigma=[10,10,10,20,20]$
- $\lambda=[10,10,2.5,25,1e-6]$
- $bias=[0,100,200,300,400]$
- $F_{27}^*=2700$

Components:

| Component | Function |
|---|---|
| $g_1$ | Rotated HGBat Function $F_{14}'$ |
| $g_2$ | Rotated Rastrigin's Function $F_9'$ |
| $g_3$ | Rotated Schwefel's Function $F_{11}'$ |
| $g_4$ | Rotated Weierstrass Function $F_6'$ |
| $g_5$ | Rotated High Conditioned Elliptic Function $F_1'$ |

Figure captions:

- Figure 21(a). 3-D map for 2-D function.
- Figure 21(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima

### 28. Composition Function 6

Parameters:

- $N=5$
- $\sigma=[10,20,30,40,50]$
- $\lambda=[2.5,10,2.5,5e-4,1e-6]$
- $bias=[0,100,200,300,400]$
- $F_{28}^*=2800$

Components:

| Component | Function |
|---|---|
| $g_1$ | Rotated Expanded Griewank's plus Rosenbrock's Function $F_{15}'$ |
| $g_2$ | Rotated HappyCat Function $F_{13}'$ |
| $g_3$ | Rotated Schwefel's Function $F_{11}'$ |
| $g_4$ | Rotated Expanded Scaffer's F6 Function $F_{16}'$ |
| $g_5$ | Rotated High Conditioned Elliptic Function $F_1'$ |

Figure captions:

- Figure 28(a). 3-D map for 2-D function.
- Figure 28(b). Contour map for 2-D function.

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima

### 29. Composition Function 7

Parameters:

- $N=3$
- $\sigma=[10,30,50]$
- $\lambda=[1,1,1]$
- $bias=[0,100,200]$
- $F_{29}^*=2900$

Components:

| Component | Function |
|---|---|
| $g_1$ | Hybrid Function 1 $F_{17}'$ |
| $g_2$ | Hybrid Function 2 $F_{18}'$ |
| $g_3$ | Hybrid Function 3 $F_{19}'$ |

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima
- Different properties for different variable subcomponents

### 30. Composition Function 8

Parameters:

- $N=3$
- $\sigma=[10,30,50]$
- $\lambda=[1,1,1]$
- $bias=[0,100,200]$
- $F_{30}^*=3000$

Components:

| Component | Function |
|---|---|
| $g_1$ | Hybrid Function 4 $F_{20}'$ |
| $g_2$ | Hybrid Function 5 $F_{21}'$ |
| $g_3$ | Hybrid Function 6 $F_{22}'$ |

Properties:

- Multi-modal
- Non-separable
- Asymmetrical
- Different properties around different local optima
- Different properties for different variable subcomponents

## 2. Evaluation Criteria

## 2.1 Experimental Setting

| Setting | Value |
|---|---|
| Problems | 30 minimization problems |
| Dimensions | $D=10,30,50,100$ |
| Initial submission dimensions | Results only for 10D and 30D are acceptable for the initial submission |
| Final version dimensions | 50D and 100D should be included in the final version |
| Runs per problem | 51 |
| MaxFES | $10000D$ |
| MaxFES for 10D | 100000 |
| MaxFES for 30D | 300000 |
| MaxFES for 50D | 500000 |
| MaxFES for 100D | 1000000 |
| Search range | $[-100,100]^D$ |
| Initialization | Uniform random initialization within the search space |
| Matlab seed example | `rand('state', sum(100*clock))` |
| Termination | Terminate at MaxFES or when error value is smaller than $10^{-8}$ |

Do not run more than 51 runs to pick the best run.

All problems have the global optimum within the given bounds; there is no need to perform search outside the given bounds.

For problem $i$:

$$
F_i(x^*)=F_i(o_i)=F_i^*
$$

## 2.2 Results Record

Record the function error value:

$$
F_i(x)-F_i(x^*)
$$

after each of the following fractions of MaxFES for each run:

```text
0.01, 0.02, 0.03, 0.05, 0.1, 0.2, 0.3,
0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0
```

Thus, 14 error values are recorded for each function for each run.

Sort the error values achieved after MaxFES in 51 runs from smallest (best) to largest (worst), and present the following statistics for the 51 runs:

- Best
- Worst
- Mean
- Median
- Standard variance

Error values smaller than $10^{-8}$ are taken as zero.

## 2.3 Algorithm Complexity

### Step a: Baseline time $T0$

Run the following test program:

```matlab
for i = 1:1000000
    x = 0.55 + (double) i;
    x = x + x;
    x = x / 2;
    x = x * x;
    x = sqrt(x);
    x = log(x);
    x = exp(x);
    x = x / (x + 2);
end
```

Computing time for the above program is $T0$.

### Step b: Function-only time $T1$

Evaluate the computing time just for Function 18. For 200000 evaluations of a certain dimension $D$, this gives $T1$.

### Step c: Complete algorithm time $T2$

The complete computing time for the algorithm with 200000 evaluations of the same $D$-dimensional Function 18 is $T2$.

### Step d: Repeated timing

Execute step c five times and obtain five $T2$ values.

$$
\hat{T2}=\operatorname{Mean}(T2)
$$

The algorithm complexity is reflected by:

$$
\hat{T2},\quad T1,\quad T0,\quad \frac{\hat{T2}-T1}{T0}
$$

Algorithm complexities are calculated for 10, 30, and 50 dimensions to show the relationship between algorithm complexity and dimension. Sufficient details on the computing system and programming language should also be provided.

In step c, the complete algorithm is executed five times to accommodate variations in execution time due to the adaptive nature of some algorithms.

Important fairness note:

- Similar programming styles should be used for all $T0$, $T1$, and $T2$.
- For example, if $m$ individuals are evaluated at the same time in the algorithm, the same style should be employed for calculating $T1$.
- If parallel calculation is employed for $T2$, the same method should be used for calculating $T0$ and $T1$.
- The complexity calculation should be fair.

## 2.4 Parameters

Participants must not search for a distinct set of parameters for each problem, dimension, etc.

Provide details on the following whenever applicable:

- All parameters to be adjusted
- Corresponding dynamic ranges
- Guidelines on how to adjust the parameters
- Estimated cost of parameter tuning in terms of number of function evaluations (FEs)
- Actual parameter values used

## 2.5 Encoding

If the algorithm requires encoding, the encoding scheme should be independent of the specific problems and governed by generic factors such as the search ranges.

## 2.6 Results Format

Participants are required to send final results to the organizers in the following format. The organizers will present an overall analysis and comparison based on these results.

Create one text document for each test function and for each dimension. File naming pattern:

```text
AlgorithmName_FunctionNo._D.txt
```

Example:

```text
PSO_5_30.txt
```

The example filename is for PSO results on test function 5 with $D=30$.

Each file contains a $14 \times 51$ matrix. The matrix format is:

| Row | Run 1 | Run 2 | ... | Run 51 |
|---|---:|---:|---:|---:|
| Function error values when FES = $0.01\cdot MaxFES$ |  |  |  |  |
| Function error values when FES = $0.02\cdot MaxFES$ |  |  |  |  |
| Function error values when FES = $0.03\cdot MaxFES$ |  |  |  |  |
| Function error values when FES = $0.05\cdot MaxFES$ |  |  |  |  |
| ... |  |  |  |  |
| Function error values when FES = $0.9\cdot MaxFES$ |  |  |  |  |
| Function error values when FES = $MaxFES$ |  |  |  |  |

Thus, $30\times4$ files for 10D, 30D, 50D, and 100D should be zipped and sent to the organizers.

Notice from the PDF: all participants are allowed to improve their algorithms further after submitting the initial version of their papers to CEC 2014. They are required to submit their results in the introduced format to the organizers after submitting the final version of the paper as soon as possible.

## 2.7 Results Template

Example metadata:

```text
Language: Matlab 2008a
Algorithm: Particle Swarm Optimizer (PSO)
```

Considering the paper length limit, only error values achieved with MaxFES need to be listed in the paper. Authors are required to send all results, i.e. the $30\times4$ files described in Section 2.6, to the organizers for better algorithm comparison.

### Table III. Results for 10D

| Func. | Best | Worst | Median | Mean | Std |
|---:|---:|---:|---:|---:|---:|
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |
| 4 |  |  |  |  |  |
| 5 |  |  |  |  |  |
| 6 |  |  |  |  |  |
| 7 |  |  |  |  |  |
| 8 |  |  |  |  |  |
| 9 |  |  |  |  |  |
| 10 |  |  |  |  |  |
| 11 |  |  |  |  |  |
| 12 |  |  |  |  |  |
| 13 |  |  |  |  |  |
| 14 |  |  |  |  |  |
| 15 |  |  |  |  |  |
| 16 |  |  |  |  |  |
| 17 |  |  |  |  |  |
| 18 |  |  |  |  |  |
| 19 |  |  |  |  |  |
| 20 |  |  |  |  |  |
| 21 |  |  |  |  |  |
| 22 |  |  |  |  |  |
| 23 |  |  |  |  |  |
| 24 |  |  |  |  |  |
| 25 |  |  |  |  |  |
| 26 |  |  |  |  |  |
| 27 |  |  |  |  |  |
| 28 |  |  |  |  |  |
| 29 |  |  |  |  |  |
| 30 |  |  |  |  |  |

### Tables IV-VI

- Table IV: Results for 30D.
- Table V: Results for 50D.
- Table VI: Results for 100D.

Use the same column structure as Table III.

### Table VII. Computational Complexity

| Dimension | $T0$ | $T1$ | $\hat{T2}$ | $(\hat{T2}-T1)/T0$ |
|---|---:|---:|---:|---:|
| $D=10$ |  |  |  |  |
| $D=30$ |  |  |  |  |
| $D=50$ |  |  |  |  |

### Parameter Reporting Template

Provide:

- All parameters to be adjusted
- Corresponding dynamic ranges
- Guidelines on how to adjust the parameters
- Estimated cost of parameter tuning in terms of number of FEs
- Actual parameter values used

## References

[1] P. N. Suganthan, N. Hansen, J. J. Liang, K. Deb, Y.-P. Chen, A. Auger, and S. Tiwari, "Problem Definitions and Evaluation Criteria for the CEC 2005 Special Session on Real-Parameter Optimization," Technical Report, Nanyang Technological University, Singapore, May 2005, and KanGAL Report #2005005, IIT Kanpur, India, 2005.

[2] J. J. Liang, B. Y. Qu, P. N. Suganthan, and Alfredo G. Hernandez-Diaz, "Problem Definitions and Evaluation Criteria for the CEC 2013 Special Session and Competition on Real-Parameter Optimization," Technical Report 201212, Computational Intelligence Laboratory, Zhengzhou University, Zhengzhou, China, and Technical Report, Nanyang Technological University, Singapore, January 2013.

[3] Joaquin Derrac, Salvador Garcia, Sheldon Hui, Francisco Herrera, and Ponnuthurai N. Suganthan, "Statistical analysis of convergence performance throughout the search: A case study with SaDE-MMTS and Sa-EPSDE-MMTS," IEEE Symposium on Differential Evolution 2013, IEEE SSCI 2013, Singapore.

[4] Nikolaus Hansen, Steffen Finck, Raymond Ros, and Anne Auger, "Real-Parameter Black-Box Optimization Benchmarking 2010: Noiseless Functions Definitions," INRIA research report RR-6829, March 24, 2012.

[5] Xiaodong Li, Ke Tang, Mohammad N. Omidvar, Zhenyu Yang, and Kai Qin, "Benchmark Functions for the CEC 2013 Special Session and Competition on Large-Scale Global Optimization," Technical Report, 2013.

[6] H.-G. Beyer and S. Finck, "HappyCat -- A Simple Function Class Where Well-Known Direct Search Algorithms Do Fail," in Proceedings of Parallel Problem Solving from Nature 12, pp. 367-376, edited by C. A. Coello Coello et al., Springer, Berlin, 2012.
