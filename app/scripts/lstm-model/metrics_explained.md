RMSE (Root Mean Squared Error)
RMSE = √(Σ(actual - predicted)² / N)
Average of squared errors, then square-rooted to return to the original units ($).
Example	Actual	Predicted	Squared Error
A	100	90	(10)² = 100
B	100	80	(20)² = 400
C	100	130	(-30)² = 900
RMSE = √((100 + 400 + 900) / 3) = √466.67 = $21.60
Why squared? Penalizes large errors more heavily. A $30 error counts 9× more than a $10 error.


MAE (Mean Absolute Error)
MAE = Σ|actual - predicted| / N
Average of absolute errors — same units as data ($).
MAE = (10 + 20 + 30) / 3 = $20.00
Difference from RMSE: No squaring. Large errors aren't disproportionately punished. RMSE ≥ MAE always (RMSE penalizes outliers more).


MAPE (Mean Absolute Percentage Error)
MAPE = Σ|(actual - predicted) / actual| / N × 100
Error as a percentage of actual values — unit-independent.
MAPE = (10/100 + 20/100 + 30/100) / 3 × 100 = 20%
Interpretation: "On average, predictions are off by 20%." The model's MAPE of 0.14% means predictions are typically within ±$93 of actual (for a $66k price).
Caveat: Breaks when actual = 0 (division by zero).


R² (R-squared, Coefficient of Determination)
R² = 1 - (SS_residual / SS_total)
SS_residual = Σ(actual - predicted)²
SS_total = Σ(actual - mean(actual))²
Measures how much variance the model explains compared to just predicting the mean.
R² value	Meaning
1.0	Perfect prediction
0.99	Excellent (this model)
0.5	Moderate — model explains half the variance
0.0	Model no better than guessing the mean
< 0	Worse than predicting the mean
This model's R² = 0.9945 → 99.45% of price variation is captured by predictions.


Summary table
Metric	Units	What it answers
RMSE	$	"Typical error in dollars?"
MAE	$	"Average error in dollars?"
MAPE	%	"Average error as % of price?"
R²	0–1	"How much variance is explained?"
RMSE and MAE are in the same units as the target (easy to interpret). MAPE is comparable across different price scales. R² gives a relative sense of fit quality (0–1 scale).