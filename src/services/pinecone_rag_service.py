"""Pinecone RAG Service with LangGraph Workflow.

This module provides a production-ready RAG service using Pinecone vector database
and LangGraph for orchestrating the retrieval and generation workflow.
"""

import os
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from operator import add

from loguru import logger
from pinecone import Pinecone, ServerlessSpec
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END


class RAGState(TypedDict):
    """State for the RAG workflow."""
    question: str
    context: List[str]
    answer: str
    relevance_score: float
    should_use_rag: bool


class PineconeRAGService:
    """Production RAG service using Pinecone and LangGraph.

    This service provides:
    - Vector similarity search using Pinecone
    - LangGraph workflow for retrieval, relevance checking, and generation
    - Document ingestion with automatic chunking
    - Configurable retrieval parameters
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Pinecone RAG Service.

        Args:
            config: Configuration for the RAG service including:
                - pinecone_api_key: Pinecone API key
                - pinecone_index: Index name
                - openai_api_key: OpenAI API key for embeddings
                - namespace: Optional namespace in Pinecone
                - top_k: Number of documents to retrieve (default: 5)
                - relevance_threshold: Minimum score for relevance (default: 0.7)
        """
        self.config = config or {}

        # Get configuration from environment or config
        self.pinecone_api_key = self.config.get("pinecone_api_key") or os.getenv("PINECONE_API_KEY")
        self.pinecone_index_name = self.config.get("pinecone_index") or os.getenv("PINECONE_INDEX", "voice-assistant-rag")
        self.openai_api_key = self.config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        self.namespace = self.config.get("namespace", "default")
        self.top_k = self.config.get("top_k", 5)
        self.relevance_threshold = self.config.get("relevance_threshold", 0.7)

        # Initialize components
        self.pc = None
        self.index = None
        self.vector_store = None
        self.embeddings = None
        self.llm = None
        self.workflow = None

        self._initialized = False

        # Try to initialize
        self._initialize()

    def _initialize(self) -> bool:
        """Initialize Pinecone, embeddings, and LangGraph workflow."""
        try:
            if not self.pinecone_api_key:
                logger.warning("PINECONE_API_KEY not set - RAG service will use fallback mode")
                return False

            if not self.openai_api_key:
                logger.warning("OPENAI_API_KEY not set - RAG service will use fallback mode")
                return False

            # Initialize Pinecone
            self.pc = Pinecone(api_key=self.pinecone_api_key)

            # Check if index exists, create if not
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.pinecone_index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {self.pinecone_index_name}")
                self.pc.create_index(
                    name=self.pinecone_index_name,
                    dimension=1536,  # OpenAI text-embedding-ada-002 dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )

            self.index = self.pc.Index(self.pinecone_index_name)

            # Initialize OpenAI embeddings
            self.embeddings = OpenAIEmbeddings(
                api_key=self.openai_api_key,
                model="text-embedding-ada-002"
            )

            # Initialize vector store
            self.vector_store = PineconeVectorStore(
                index=self.index,
                embedding=self.embeddings,
                namespace=self.namespace
            )

            # Initialize LLM for generation
            self.llm = ChatOpenAI(
                api_key=self.openai_api_key,
                model="gpt-4o-mini",
                temperature=0.3
            )

            # Build the LangGraph workflow
            self._build_workflow()

            self._initialized = True
            logger.info("Pinecone RAG Service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone RAG Service: {e}")
            self._initialized = False
            return False

    def _build_workflow(self):
        """Build the LangGraph workflow for RAG."""

        # Define workflow nodes
        def retrieve(state: RAGState) -> RAGState:
            """Retrieve relevant documents from Pinecone."""
            question = state["question"]

            try:
                # Search for similar documents
                results = self.vector_store.similarity_search_with_score(
                    question,
                    k=self.top_k
                )

                # Extract context and calculate average relevance
                context = []
                scores = []

                for doc, score in results:
                    context.append(doc.page_content)
                    scores.append(score)

                avg_score = sum(scores) / len(scores) if scores else 0.0

                return {
                    **state,
                    "context": context,
                    "relevance_score": avg_score,
                    "should_use_rag": avg_score >= self.relevance_threshold
                }

            except Exception as e:
                logger.error(f"Retrieval error: {e}")
                return {
                    **state,
                    "context": [],
                    "relevance_score": 0.0,
                    "should_use_rag": False
                }

        def check_relevance(state: RAGState) -> str:
            """Decide whether to use RAG or fallback."""
            if state["should_use_rag"] and state["context"]:
                return "generate"
            return "fallback"

        def generate(state: RAGState) -> RAGState:
            """Generate answer using retrieved context."""
            question = state["question"]
            context = "\n\n".join(state["context"])

            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful assistant that answers questions based on the provided context.

Use ONLY the information from the context to answer the question.
If the context doesn't contain enough information to fully answer the question, say so.
Keep your response concise and natural for voice output.

Context:
{context}"""),
                ("human", "{question}")
            ])

            chain = prompt | self.llm | StrOutputParser()

            try:
                answer = chain.invoke({
                    "context": context,
                    "question": question
                })
                return {**state, "answer": answer}
            except Exception as e:
                logger.error(f"Generation error: {e}")
                return {**state, "answer": f"I encountered an error generating a response: {str(e)}"}

        def fallback(state: RAGState) -> RAGState:
            """Provide fallback response when no relevant context found."""
            return {
                **state,
                "answer": f"I don't have specific information about that in my knowledge base. The question was: {state['question']}"
            }

        # Build the graph
        workflow = StateGraph(RAGState)

        # Add nodes
        workflow.add_node("retrieve", retrieve)
        workflow.add_node("generate", generate)
        workflow.add_node("fallback", fallback)

        # Add edges
        workflow.set_entry_point("retrieve")
        workflow.add_conditional_edges(
            "retrieve",
            check_relevance,
            {
                "generate": "generate",
                "fallback": "fallback"
            }
        )
        workflow.add_edge("generate", END)
        workflow.add_edge("fallback", END)

        # Compile the workflow
        self.workflow = workflow.compile()
        logger.info("LangGraph RAG workflow compiled successfully")

    async def get_response(self, question: str) -> str:
        """Get a response to a user question using RAG.

        Args:
            question: The user's question

        Returns:
            The response to the question
        """
        logger.info(f"Processing question through RAG: {question}")

        if not self._initialized:
            logger.warning("RAG service not initialized, using fallback")
            return self._fallback_response(question)

        try:
            # Run the workflow
            initial_state: RAGState = {
                "question": question,
                "context": [],
                "answer": "",
                "relevance_score": 0.0,
                "should_use_rag": False
            }

            # Execute workflow (sync execution wrapped for async)
            result = self.workflow.invoke(initial_state)

            logger.info(f"RAG response generated with relevance score: {result['relevance_score']:.2f}")
            return result["answer"]

        except Exception as e:
            logger.error(f"Error in RAG workflow: {e}")
            return self._fallback_response(question)

    def _fallback_response(self, question: str) -> str:
        """Provide a fallback response when RAG is unavailable."""
        return f"I apologize, but my knowledge retrieval system is currently unavailable. Please try again later or rephrase your question."

    async def ingest_documents(self, documents: List[Dict[str, str]], chunk_size: int = 1000, chunk_overlap: int = 200) -> Dict[str, Any]:
        """Ingest documents into the Pinecone vector store.

        Args:
            documents: List of documents with 'content' and optional 'metadata'
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks

        Returns:
            Ingestion statistics
        """
        if not self._initialized:
            return {"success": False, "error": "RAG service not initialized"}

        try:
            # Create text splitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )

            # Process documents
            all_chunks = []
            for doc in documents:
                content = doc.get("content", "")
                metadata = doc.get("metadata", {})

                # Split into chunks
                chunks = text_splitter.split_text(content)

                # Create Document objects
                for i, chunk in enumerate(chunks):
                    chunk_metadata = {
                        **metadata,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                    all_chunks.append(Document(page_content=chunk, metadata=chunk_metadata))

            # Add to vector store
            self.vector_store.add_documents(all_chunks)

            logger.info(f"Ingested {len(all_chunks)} chunks from {len(documents)} documents")

            return {
                "success": True,
                "documents_processed": len(documents),
                "chunks_created": len(all_chunks)
            }

        except Exception as e:
            logger.error(f"Document ingestion error: {e}")
            return {"success": False, "error": str(e)}

    async def ingest_text(self, text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest a single text into the vector store.

        Args:
            text: Text content to ingest
            metadata: Optional metadata

        Returns:
            Ingestion result
        """
        return await self.ingest_documents([{
            "content": text,
            "metadata": metadata or {}
        }])

    def delete_namespace(self, namespace: str = None) -> bool:
        """Delete all vectors in a namespace.

        Args:
            namespace: Namespace to delete (defaults to current namespace)

        Returns:
            Success status
        """
        if not self._initialized:
            return False

        try:
            ns = namespace or self.namespace
            self.index.delete(delete_all=True, namespace=ns)
            logger.info(f"Deleted all vectors in namespace: {ns}")
            return True
        except Exception as e:
            logger.error(f"Error deleting namespace: {e}")
            return False

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the RAG service configuration.

        Args:
            config: New configuration parameters
        """
        self.config.update(config)

        # Update relevant parameters
        if "top_k" in config:
            self.top_k = config["top_k"]
        if "relevance_threshold" in config:
            self.relevance_threshold = config["relevance_threshold"]

        logger.info(f"Updated RAG config: {config}")

    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration.

        Returns:
            Current configuration dictionary
        """
        return {
            **self.config,
            "top_k": self.top_k,
            "relevance_threshold": self.relevance_threshold,
            "namespace": self.namespace,
            "index_name": self.pinecone_index_name
        }

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the RAG service.

        Returns:
            Dictionary containing service status
        """
        status = {
            "initialized": self._initialized,
            "config": self.get_config(),
            "ready": self._initialized
        }

        if self._initialized and self.index:
            try:
                stats = self.index.describe_index_stats()
                status["index_stats"] = {
                    "total_vectors": stats.total_vector_count,
                    "namespaces": dict(stats.namespaces) if stats.namespaces else {}
                }
            except Exception as e:
                status["index_stats"] = {"error": str(e)}

        return status


# Factory function to create the appropriate RAG service
def create_rag_service(config: Dict[str, Any] = None) -> "PineconeRAGService":
    """Factory function to create a RAG service instance.

    Args:
        config: Configuration dictionary

    Returns:
        Configured RAG service instance
    """
    rag_type = config.get("type", "pinecone") if config else "pinecone"

    if rag_type == "pinecone":
        return PineconeRAGService(config.get("config", {}) if config else {})
    else:
        # Default to Pinecone
        return PineconeRAGService(config.get("config", {}) if config else {})
