FROM mambaorg/micromamba:1.5.8

LABEL org.opencontainers.image.source=https://github.com/openforcefield/openff-bespokefit
LABEL org.opencontainers.image.description="Automated tools for the generation of bespoke SMIRNOFF format parameters for individual molecules."
LABEL org.opencontainers.image.licenses=MIT

# Don't buffer stdout & stderr streams, so if there is a crash no partial buffer output is lost
# https://docs.python.org/3/using/cmdline.html#cmdoption-u
ENV PYTHONUNBUFFERED=1

COPY --chown=$MAMBA_USER:$MAMBA_USER devtools/conda-envs/bespokefit-server.yaml /tmp/env.yaml
COPY --chown=$MAMBA_USER:$MAMBA_USER openff /tmp/openff
COPY --chown=$MAMBA_USER:$MAMBA_USER LICENSE README.md setup.cfg setup.py /tmp/
RUN micromamba install -y -n base git -f /tmp/env.yaml && \
    micromamba clean --all --yes

# Ensure that conda environment is automatically activated
# https://github.com/mamba-org/micromamba-docker#running-commands-in-dockerfile-within-the-conda-environment
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip install --no-deps -e .

WORKDIR /home/mambauser
RUN mkdir /home/mambauser/.OpenEye
ENV OE_LICENSE=/home/mambauser/.OpenEye/oe_license.txt