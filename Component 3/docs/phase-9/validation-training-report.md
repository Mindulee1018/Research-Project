# Validation Training Report

This report summarizes the **latest local validation/test split** result for the Sentence-BERT classifier.

Scope:
- Includes only validation/test split metrics
- Label order for the confusion matrix: `DISINFO`, `HATE`, `NORMAL`

### Summary

- Accuracy: `0.8546`
- Macro F1: `0.8627`
- Weighted F1: `0.8548`
- Total support: `8881`

### Confusion Matrix

| True \ Predicted | DISINFO | HATE | NORMAL |
| --- | ---: | ---: | ---: |
| DISINFO | 1639 | 27 | 116 |
| HATE | 38 | 2376 | 426 |
| NORMAL | 119 | 565 | 3575 |

### Classification Report

| Label | Precision | Recall | F1-score | Support |
| --- | ---: | ---: | ---: | ---: |
| DISINFO | 0.9126 | 0.9198 | 0.9162 | 1782 |
| HATE | 0.8005 | 0.8366 | 0.8182 | 2840 |
| NORMAL | 0.8684 | 0.8394 | 0.8536 | 4259 |
| Macro Avg | 0.8605 | 0.8653 | 0.8627 | 8881 |
| Weighted Avg | 0.8555 | 0.8546 | 0.8548 | 8881 |

### Notes

- This is the strongest available validation/test run in the local artifact set.
- `DISINFO` is the best-performing class in this run.
- `HATE` remains the weakest class, but still performs well.
- `NORMAL` is stable and strong in the validation split.
