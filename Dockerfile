FROM langchain/langgraph-api:3.11



# -- Adding local package . --
ADD . /deps/web-research-agent
# -- End of local package . --

# -- Installing all local dependencies --
RUN PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -c /api/constraints.txt -e /deps/*
# -- End of local dependencies install --
ENV LANGSERVE_GRAPHS='{"agent": "/deps/web-research-agent/src/react_agent/graph.py:graph"}'



WORKDIR /deps/web-research-agent
