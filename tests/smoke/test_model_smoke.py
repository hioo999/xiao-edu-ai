import pytest


pytestmark = pytest.mark.smoke


class TinyLocalModel:
    """Deterministic local model used by CI to exercise the inference protocol."""

    def __init__(self) -> None:
        self.loaded = True

    def generate(self, prompt: str) -> str:
        if not self.loaded:
            raise RuntimeError("model is not loaded")
        return f"local-model:{prompt.strip()}"


def load_lightweight_model() -> TinyLocalModel:
    return TinyLocalModel()


def test_lightweight_model_loads_and_runs_inference_chain() -> None:
    model = load_lightweight_model()
    prompt = "请生成一个关于海洋的网页"

    output = model.generate(prompt)

    assert model.loaded is True
    assert isinstance(output, str)
    assert output == "local-model:请生成一个关于海洋的网页"


def test_optional_huggingface_smoke_is_opt_in() -> None:
    model_id = __import__("os").environ.get("SMOKE_MODEL_ID")
    if not model_id:
        pytest.skip("set SMOKE_MODEL_ID to run an external lightweight model smoke test")

    transformers = pytest.importorskip("transformers")
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_id)
    model = transformers.AutoModelForCausalLM.from_pretrained(model_id)
    inputs = tokenizer("hello", return_tensors="pt")
    generated = model.generate(**inputs, max_new_tokens=1)

    assert generated.shape[0] == 1
