# Component 2 Overview

Title: Concept Drift Detection Based Adaptive Learning Framework Using Incremental Learning

# Main purpose
1. Detects concept drift in incoming data
2. Learns new hate-related terms and variants
3. Incrementally updates the classifier model when drift is detected

# Overall Flow
Component 1 model predictions / daily batch CSV
        ↓
Component 2 preprocessing
        ↓
Sinhala normalization + variant resolving
        ↓
Drift detection
        ↓
Trigger decision
        ↓
Adaptive lexicon update
        ↓
Incremental model fine-tuning
        ↓
Save new model version
        ↓
Evaluate base vs adaptive model
        ↓
Show results in dashboard


# Input Data
Component 2 receives batch files from Component 1.
These batch files contain fields such as:
text / Cleaned Comment
Label
Hate
Disinfo
Normal
hate word / Hate Words
batch_no

For drift detection, system mainly uses:
Hate label
hate words / detected terms
batch number

For model fine-tuning, your system uses:
cleaned text
label

# Preprocessing and Term Handling
1. Text normalization
    * removing zero-width characters
    * normalizing Unicode
    * removing unnecessary punctuation
    * lowercasing English text
    * cleaning whitespace

2. Variant resolution
Sinhala hate words often appear in different forms. For example, the same base word can appear with suffixes or spelling variations.
Your system handles this using:
    * Morfessor-based stemming
    * automatic suffix mining
    * manual alias mapping
    * variant grouping
    * canonical term mapping
This means different word variants can be grouped under one canonical form.
variant word forms → canonical hate term
# This helps the system avoid treating every spelling variation as a completely new word.

-----------------------------------------------------------

# Drift Detection Methods

1. Target drift detection - checks whether the hate rate is changing over time.
---------------------------------------------------
hate_rate = number of hate samples / total samples in batch

Use : ADWIN drift detector

2. Data drift detection using JSD
The system checks whether the distribution of hate terms has changed compared to previous batches.

Use: Jensen-Shannon Divergence

This compares
current batch hate-term distribution
vs
baseline hate-term distribution

3. Concept proxy drift
Concept drift means the relationship between terms and labels changes.

Since full model-internal concept drift is difficult to measure directly, my system uses a proxy:  P(Hate | term)

The system checks whether the probability of a term appearing in hate comments changes between the current batch and previous baseline batches.

Term A was mostly normal before
Term A now appears mostly in hate comments
→ possible concept drift

4. New term rate
checks how many new hate-related terms appear in the current batch

new_term_rate = new hate terms / unique hate terms in batch

# Trigger Decision
The system combines drift signals using a voting-based trigger rule.
    * target_drift
    * data_drift
    * concept_proxy
    * new_term_flag

if enough history exists and
   multiple drift signals are active
   or new term rate is high:
       trigger adaptive update


# Adaptive Lexicon Update
When a trigger is detected, Component 2 updates the adaptive hate-term lexicon.

The lexicon stores information like:
* term
* hate_count
* total_count
* weight
* first_seen_batch
* last_updated_batch

This means the system can immediately learn new hate-related terms even before the classifier is fine-tuned.

The lexicon update is lightweight and can happen more often than full model fine-tuning.

# Incremental Model Learning

This is the part that makes your component a true adaptive learning framework.

When a drift trigger occurs, the system fine-tunes the Component 1 Hugging Face classifier using recent drift-related batches.

Important point: The model is not trained from scratch.

Instead, it does:
Load existing base model or latest adaptive model
        ↓
Fine-tune using recent labelled batch data
        ↓
Save as a new model version

# Why Only the Classifier Is Updated

Component 1 has two model parts:
1. Hugging Face PyTorch classifier
2. ONNX token-level hate-word detector

Component 2 updates only the classifier model.
1. The classifier decides final HATE / DISINFO / NORMAL prediction.
2. The ONNX token model needs BIO token-level labels.
3. Your daily batches mainly contain comment-level labels.

So the ONNX model remains fixed, while new hate terms are handled through:
    * adaptive lexicon
    * variant resolver
    * manual aliases