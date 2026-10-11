# Experiments: measuring keystroke verification

Everything lives in **one notebook**: `keystroke_verification.ipynb`.
It is separate from the Streamlit app. Its job is to *measure* how well keystroke
verification methods work on real data, so the thresholds and model used in the
app can be chosen from evidence.

## Data

Download `DSL-StrongPasswordData.csv` from <https://www.cs.cmu.edu/~keystroke/>
and put it in `experiments/data/` (git-ignored).
Expected MD5: `470235f96568f28f9ea0da62234ec857`.

- 51 typists, each typed `.tie5Roanl` 400 times (8 sessions x 50).
- 31 timing features per attempt (seconds): `H.*` hold time, `DD.*` key-down to
  key-down, `UD.*` key-up to key-down.
- Please cite: Killourhy & Maxion, *Comparing Anomaly-Detection Algorithms for
  Keystroke Dynamics*, DSN 2009.

## Run

```
pip install -r experiments/requirements.txt
```

Open `experiments/keystroke_verification.ipynb` in VS Code (choose the project's
`.venv` as the kernel) or in Jupyter and press **Run All** (about 15 seconds).
The notebook already contains its saved outputs, so you can also just read it.

It writes `results/results_summary.csv`, `results/results_per_user.csv` and
`results/results_eer_boxplot.png`.

## What the notebook does

| Part | Content |
|---|---|
| Part 1 (steps 1-10) | the idea with **one user**: profile, distance, threshold, FAR / FRR, EER |
| Part 2 (steps 11-14) | a fair test on **all 51 users**, comparing 7 methods |
| Part 3 | results, limits, next steps |

**Protocol** (same as the CMU paper), per user: train on their first 200 attempts;
test on their last 200 (genuine) and on the first 5 attempts of each of the other
50 users (250 impostor attempts).

**Metrics:** FAR (impostor accepted), FRR (owner rejected), EER (error where
FAR = FRR, lower is better), and FRR when FAR <= 1 %.

## Results (average over 51 users)

| Method | EER | FRR at FAR 1 % |
|---|---|---|
| Z-score distance | 9.31 % | 42.04 % |
| Scaled Manhattan | 9.60 % | 43.31 % |
| TrueTestAuth profile (idea used in the app) | 10.44 % | 37.84 % |
| One-class SVM | 10.67 % | 48.76 % |
| Mahalanobis | 11.00 % | 35.34 % |
| Manhattan | 15.29 % | 68.57 % |
| Euclidean | 17.05 % | 75.60 % |

Scaled Manhattan, Mahalanobis, Manhattan and Euclidean are very close to the
figures in the CMU paper, which suggests the data loading, protocol and metrics
are correct.

## Adding a new method

Write a function that takes the training matrix and returns a scoring function
(higher score = more likely an impostor), then add it to the `methods` dictionary
in Step 12 and re-run:

```python
def my_method(train):
    mean = train.mean(axis=0)
    return lambda X: ...      # one score per row of X
```

Planned: a Siamese network, then raw-sequence LSTM / Transformer models on a
dataset with raw key events (for example the Aalto 136M keystrokes data).

## Important limits

- CMU is a **fixed password** typed in a lab. It cannot test free-text typing
  (the exam-answer case), so it cannot validate the app's "free" context.
- The 31 CMU features are not the app's 13 features. The `TrueTestAuth profile`
  row applies the same *idea* (RMS z-distance with a minimum spread) to CMU's
  features, not the exact app code.
