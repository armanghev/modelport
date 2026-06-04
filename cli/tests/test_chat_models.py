from modelport_agent_config.chat_models import filter_chat_models, is_agent_chat_model
from modelport_agent_config.modelport import ProviderModel


def _model(
    model_id: str,
    *,
    output: tuple[str, ...] = (),
    input_mod: tuple[str, ...] = (),
    architecture: str | None = None,
) -> ProviderModel:
    return ProviderModel(
        id=model_id,
        input_modalities=input_mod,
        output_modalities=output,
        architecture_modality=architecture,
    )


def test_allows_gemini_25_flash_text_output():
    assert is_agent_chat_model(
        _model(
            "models/gemini-2.5-flash",
            output=("text",),
            input_mod=("text", "image"),
            architecture="text+image->text",
        )
    )


def test_excludes_gemini_20_flash_without_metadata():
    assert not is_agent_chat_model(_model("models/gemini-2.0-flash"))


def test_excludes_embedding_and_tts():
    assert not is_agent_chat_model(
        _model("models/gemini-embedding-001", output=("embeddings",), input_mod=("text",))
    )
    assert not is_agent_chat_model(_model("models/gemini-2.5-flash-preview-tts"))
    assert not is_agent_chat_model(
        _model(
            "models/gemini-3.1-flash-tts-preview",
            output=("speech",),
            input_mod=("text",),
        )
    )


def test_excludes_image_generation_models():
    assert not is_agent_chat_model(
        _model(
            "models/gemini-2.5-flash-image",
            output=("image", "text"),
            input_mod=("image", "text"),
        )
    )


def test_filter_chat_models_counts_excluded():
    models = [
        _model("models/gemini-2.5-flash", output=("text",)),
        _model("models/gemini-2.0-flash"),
        _model("models/gemini-embedding-001", output=("embeddings",)),
    ]
    result = filter_chat_models(models)
    assert len(result.included) == 1
    assert result.included[0].id == "models/gemini-2.5-flash"
    assert result.excluded_count == 2
