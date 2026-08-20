from tools.evaluate_claim_admission_goldset import summarize_predictions


def test_summarize_predictions_reports_accuracy_and_confusion() -> None:
    report = summarize_predictions([
        {"gold_label": "KOSIS_PIPELINE_ELIGIBLE", "predicted_label": "KOSIS_PIPELINE_ELIGIBLE"},
        {"gold_label": "MULTI_CLAIM_SPLIT_REQUIRED", "predicted_label": "KOSIS_PIPELINE_ELIGIBLE"},
    ])

    assert report["evaluated"] == 2
    assert report["correct"] == 1
    assert report["accuracy"] == 0.5
    assert report["confusion"] == {
        "KOSIS_PIPELINE_ELIGIBLE -> KOSIS_PIPELINE_ELIGIBLE": 1,
        "MULTI_CLAIM_SPLIT_REQUIRED -> KOSIS_PIPELINE_ELIGIBLE": 1,
    }
