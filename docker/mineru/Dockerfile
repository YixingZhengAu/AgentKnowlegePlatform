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
#
# torch 必须显式走 pytorch 的 cpu 索引。**别信"arm64 上 PyPI 的 torch 就是 CPU 版"** ——
# 现在 PyPI 的 linux-aarch64 torch wheel 会带一整套 nvidia cu13 依赖(libcufft 等),
# 镜像多出好几个 GB,在 30GiB 的机器上直接 "no space left on device"(2026-08 在 t4g 上实测)。
# 分两步装:先从 cpu 索引钉住 torch/torchvision,再装 mineru —— 那时依赖已满足,不会被换回 PyPI 版。
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0 torchvision==0.28.0

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
