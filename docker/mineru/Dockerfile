# MinerU 本地部署(Docker,CPU / linux-arm64)
# 说明:官方镜像基于 CUDA+sglang(amd64),在 Apple Silicon 上不可用,
# 所以自建一个只装 pipeline 后端的最小镜像。
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# opencv / pdf 渲染需要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# 只装 pipeline 后端:torch(CPU)+ transformers + onnxruntime,不装 vllm/sglang/gradio
# linux/arm64 上 PyPI 的 torch wheel 本身就是 CPU 版,无需 pytorch cpu 索引
# six:mineru 3.4.5 的 pipeline OCR 代码 import six 但没写进依赖(实测踩坑,必须补)
RUN uv pip install --system "mineru[pipeline]==3.4.5" six

# 模型权重缓存目录(挂 named volume,避免每次重下)
ENV HF_HOME=/models/hf \
    MODELSCOPE_CACHE=/models/modelscope \
    MINERU_MODEL_SOURCE=huggingface \
    MINERU_DEVICE_MODE=cpu

WORKDIR /work
ENTRYPOINT []
CMD ["bash"]
