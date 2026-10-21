from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
import os

# client = MemoryClient(region_name=os.environ.get("AWS_REGION", "eu-north-1"))

# memory = client.create_memory_and_wait(
#     name="MyAgentMemory",
#     description="Memory with all built-in strategies",
#     strategies=[
#         {
#             "summaryMemoryStrategy": {
#                 "name": "SessionSummarizer",
#                 "namespaceTemplates": ["/summaries/{actorId}/{sessionId}/"],
#             }
#         },
#         {
#             "userPreferenceMemoryStrategy": {
#                 "name": "PreferenceLearner",
#                 "namespaceTemplates": ["/preferences/{actorId}/"],
#             }
#         },
#         {
#             "semanticMemoryStrategy": {
#                 "name": "FactExtractor",
#                 "namespaceTemplates": ["/facts/{actorId}/"],
#             }
#         },
#     ],
# )

# MEMORY_ID = memory.get("id")

# if MEMORY_ID is None:
#     raise ValueError("Failed to create memory and obtain MEMORY_ID.")


def configure_memory_session_manager(
    session_id, actor_id
) -> AgentCoreMemorySessionManager | None:
    pass
    # retrieval_config = {
    #     f"/facts/{actor_id}": RetrievalConfig(top_k=3, relevance_score=0.5),
    #     f"/summaries/{actor_id}/{session_id}": RetrievalConfig(
    #         top_k=3, relevance_score=0.5
    #     ),
    # }
    # agent_core_memory_config = AgentCoreMemoryConfig(
    #     memory_id=str(MEMORY_ID),
    #     session_id=session_id,
    #     actor_id=actor_id,
    #     retrieval_config=retrieval_config,
    # )
    # return AgentCoreMemorySessionManager(
    #     agent_core_memory_config, region_name=os.environ.get("AWS_REGION", "eu-north-1")
    # )
