wf = Workflow()


# Local test or dev execution - context manager makes sure local processors
# are instantiated and injected.

with slay.run_local():
    wf = Workflow()
    params = Parameters()
    result = wf.run(params=params)
    print(result)


# A "marker" to designate which processors should be deployed as public remote
# service points. Depenedency processors will also be deployed, but only as
# "internal" services, not as a "public" sevice endpoint.
slay.deploy_remotely([Workflow])
########################################################################################

IMAGE_TRANSFORMERS_GPU = (
    slay.Image()
    .cuda("12.8")
    .pip_requirements_txt("common_requirements.txt")
    .pip_install("transformers")
)


class MistraLLMConfig(pydantic.BaseModel):
    hf_model_name: str


class MistralLLM(slay.ProcessorBase[MistraLLMConfig]):

    default_config = slay.Config(
        image=IMAGE_TRANSFORMERS_GPU,
        resources=slay.Resources().cpu(12).gpu("A100"),
        user_config=MistraLLMConfig(hf_model_name="EleutherAI/mistral-6.7B"),
    )

    def __init__(
        self,
        config: slay.Config = slay.provide_config(),
    ) -> None:
        super().__init__(config)
        try:
            subprocess.check_output(["nvidia-smi"], text=True)
        except:
            raise RuntimeError(
                f"Cannot run `{self.__class__}`, because host has no CUDA."
            )
        import transformers

        model_name = config.user_config.hf_model_name
        tokenizer = transformers.AutoTokenizer.from_pretrained(model_name)
        model = transformers.AutoModelForCausalLM.from_pretrained(model_name)
        self._model = transformers.pipeline(
            "text-generation", model=model, tokenizer=tokenizer
        )

    def llm_gen(self, data: str) -> str:
        return self._model(data, max_length=50)


########################################################################################

mistral: MistralLLM = slay.provide(MistralLLM)


self._mistral = mistral


########################################################################################
class FakeMistralLLM(slay.ProcessorBase):
    def llm_gen(self, data: str) -> str:
        return data.upper()


with slay.run_local():
    text_to_num = TextToNum(mistral=FakeMistralLLM())
    wf = Workflow(text_to_num=text_to_num)
    params = Parameters()
    result = wf.run(params=params)
    print(result)


########################################################################################
class MistralP(Protocol):
    def __init__(self, config: slay.Config) -> None:
        ...

    def llm_gen(self, data: str) -> str:
        ...
