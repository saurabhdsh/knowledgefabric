import React, { useState } from 'react';
import { XMarkIcon, DocumentDuplicateIcon, CheckIcon, CodeBracketIcon, CommandLineIcon } from '@heroicons/react/24/outline';

interface FabricEndpointsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  fabricId: string;
  fabricName: string;
}

const FabricEndpointsDialog: React.FC<FabricEndpointsDialogProps> = ({
  isOpen,
  onClose,
  fabricId,
  fabricName
}) => {
  const [copiedEndpoint, setCopiedEndpoint] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'endpoints' | 'langchain' | 'python' | 'javascript'>('endpoints');

  const endpoints = [
    {
      name: 'Query Knowledge Fabric',
      method: 'POST',
      endpoint: `/api/v1/knowledge/query/${fabricId}`,
      description: 'Ask questions about your knowledge fabric',
      example: {
        request: {
          query: 'What are the claims mentioned in this document?',
          llm_provider: 'openai'
        },
        response: {
          success: true,
          message: 'Knowledge base query completed',
          data: {
            fabric_id: fabricId,
            fabric_name: fabricName,
            query: 'What are the claims mentioned in this document?',
            answer: 'Based on the document content...',
            confidence: 0.8,
            model_status: 'trained',
            relevant_chunks_found: 1,
            llm_provider: 'openai',
            processing_time: '2.1s'
          }
        }
      }
    },
    {
      name: 'Validate Knowledge Base',
      method: 'POST',
      endpoint: `/api/v1/knowledge/validate-knowledge/${fabricId}`,
      description: 'Test if the model understands your knowledge base',
      example: {
        request: {
          questions: ['What is this document about?', 'What are the key points?']
        },
        response: {
          success: true,
          message: 'Knowledge base validation completed',
          data: {
            fabric_id: fabricId,
            fabric_name: fabricName,
            model_status: 'trained',
            validation_score: 0.85,
            test_questions: 2,
            results: [
              {
                question: 'What is this document about?',
                response: 'Based on the knowledge fabric...',
                confidence: 0.85,
                is_relevant: true
              }
            ],
            overall_assessment: 'excellent'
          }
        }
      }
    },
    {
      name: 'Get Fabric Status',
      method: 'GET',
      endpoint: `/api/v1/knowledge/`,
      description: 'Get information about all knowledge fabrics',
      example: {
        request: {},
        response: {
          success: true,
          data: [
            {
              id: fabricId,
              name: fabricName,
              model_status: 'trained',
              last_training: '2025-07-22 12:43:50',
              chunks_count: 150,
              storage_size: '2.5MB'
            }
          ]
        }
      }
    },
    {
      name: 'Get API Key Status',
      method: 'GET',
      endpoint: `/api/v1/knowledge/api-keys/status`,
      description: 'Check status of LLM providers and API keys',
      example: {
        request: {},
        response: {
          success: true,
          message: 'API key status retrieved successfully',
          data: {
            default_provider: 'openai',
            available_providers: [
              {
                id: 'openai',
                name: 'OpenAI GPT-4',
                description: 'Advanced reasoning with GPT-4',
                has_api_key: true
              }
            ],
            providers_with_keys: 1
          }
        }
      }
    }
  ];

  const langchainExamples = {
    basic: `from langchain.agents import Tool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
import requests

# Knowledge Fabric Tool
class KnowledgeFabricTool:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric for information"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": query})
        data = response.json()
        
        if data.get("success"):
            return data["data"]["answer"]
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize the tool
knowledge_tool = KnowledgeFabricTool("${fabricId}")

# Create LangChain tool
tool = Tool(
    name="knowledge_fabric",
    description="Query the knowledge fabric for specific information about documents and processes",
    func=knowledge_tool.query_knowledge
)

# Create agent
llm = ChatOpenAI(temperature=0)
agent = create_openai_functions_agent(llm, [tool], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[tool], verbose=True)

# Use the agent
result = agent_executor.invoke({
    "input": "What are the key stakeholders mentioned in the knowledge fabric?"
})`,

    advanced: `from langchain.agents import Tool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import requests
import json

class EnhancedKnowledgeFabricTool:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric with detailed response"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={
            "query": query,
            "llm_provider": "openai"
        })
        data = response.json()
        
        if data.get("success"):
            result = data["data"]
            return f"""Answer: {result['answer']}
Confidence: {result['confidence']}
Processing Time: {result['processing_time']}
Relevant Chunks: {result['relevant_chunks_found']}"""
        else:
            return f"Error: {data.get('message', 'Unknown error')}"
    
    def validate_knowledge(self, questions: list) -> str:
        """Validate the knowledge base with custom questions"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        data = response.json()
        
        if data.get("success"):
            result = data["data"]
            return f"""Validation Score: {result['validation_score']}
Assessment: {result['overall_assessment']}
Questions Tested: {result['test_questions']}"""
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize enhanced tool
enhanced_tool = EnhancedKnowledgeFabricTool("${fabricId}")

# Create multiple tools
query_tool = Tool(
    name="query_knowledge_fabric",
    description="Query the knowledge fabric for specific information",
    func=enhanced_tool.query_knowledge
)

validate_tool = Tool(
    name="validate_knowledge_fabric",
    description="Validate the knowledge base with custom questions",
    func=enhanced_tool.validate_knowledge
)

# Create agent with custom prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an AI assistant that helps users query and validate knowledge fabrics. Use the available tools to provide accurate information."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

llm = ChatOpenAI(temperature=0)
agent = create_openai_functions_agent(llm, [query_tool, validate_tool], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[query_tool, validate_tool], verbose=True)

# Example usage
result = agent_executor.invoke({
    "input": "What are the claims procedures and validate if the knowledge base understands this topic?",
    "chat_history": []
})`
  };

  const pythonExamples = {
    basic: `import requests
import json

class KnowledgeFabricClient:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query(self, question: str) -> dict:
        """Query the knowledge fabric"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": question})
        return response.json()
    
    def validate(self, questions: list) -> dict:
        """Validate the knowledge base"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        return response.json()

# Usage
client = KnowledgeFabricClient("${fabricId}")

# Query the knowledge fabric
result = client.query("What are the key stakeholders?")
print(f"Answer: {result['data']['answer']}")
print(f"Confidence: {result['data']['confidence']}")`,

    advanced: `import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class QueryResult:
    answer: str
    confidence: float
    processing_time: str
    relevant_chunks: int
    fabric_name: str

class AdvancedKnowledgeFabricClient:
    def __init__(self, fabric_id: str, base_url: str = "http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query(self, question: str, llm_provider: str = "openai") -> QueryResult:
        """Query the knowledge fabric with detailed response"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={
            "query": question,
            "llm_provider": llm_provider
        })
        data = response.json()
        
        if data.get("success"):
            result_data = data["data"]
            return QueryResult(
                answer=result_data["answer"],
                confidence=result_data["confidence"],
                processing_time=result_data["processing_time"],
                relevant_chunks=result_data["relevant_chunks_found"],
                fabric_name=result_data["fabric_name"]
            )
        else:
            raise Exception(f"Query failed: {data.get('message', 'Unknown error')}")
    
    def validate_knowledge(self, questions: List[str]) -> Dict:
        """Validate the knowledge base"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        return response.json()
    
    def get_status(self) -> Dict:
        """Get fabric status"""
        url = f"{self.base_url}/api/v1/knowledge/"
        response = requests.get(url)
        return response.json()

# Usage example
client = AdvancedKnowledgeFabricClient("${fabricId}")

try:
    # Query with specific LLM provider
    result = client.query("What are the claims procedures?", llm_provider="openai")
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence}")
    print(f"Processing Time: {result.processing_time}")
    
    # Validate knowledge base
    validation = client.validate_knowledge([
        "What is this document about?",
        "What are the key procedures?"
    ])
    print(f"Validation Score: {validation['data']['validation_score']}")
    
except Exception as e:
    print(f"Error: {e}")`
  };

  const javascriptExamples = {
    basic: `class KnowledgeFabricClient {
    constructor(fabricId, baseUrl = 'http://localhost:8000') {
        this.fabricId = fabricId;
        this.baseUrl = baseUrl;
    }
    
    async query(question) {
        const url = \`\${this.baseUrl}/api/v1/knowledge/query/\${this.fabricId}\`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: question })
        });
        return await response.json();
    }
    
    async validate(questions) {
        const url = \`\${this.baseUrl}/api/v1/knowledge/validate-knowledge/\${this.fabricId}\`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ questions })
        });
        return await response.json();
    }
}

// Usage
const client = new KnowledgeFabricClient('${fabricId}');

// Query the knowledge fabric
client.query('What are the key stakeholders?')
    .then(result => {
        console.log('Answer:', result.data.answer);
        console.log('Confidence:', result.data.confidence);
    })
    .catch(error => console.error('Error:', error));`,

    advanced: `class AdvancedKnowledgeFabricClient {
    constructor(fabricId, baseUrl = 'http://localhost:8000') {
        this.fabricId = fabricId;
        this.baseUrl = baseUrl;
    }
    
    async query(question, llmProvider = 'openai') {
        const url = \`\${this.baseUrl}/api/v1/knowledge/query/\${this.fabricId}\`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: question,
                llm_provider: llmProvider 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            return {
                answer: data.data.answer,
                confidence: data.data.confidence,
                processingTime: data.data.processing_time,
                relevantChunks: data.data.relevant_chunks_found,
                fabricName: data.data.fabric_name
            };
        } else {
            throw new Error(data.message || 'Query failed');
        }
    }
    
    async validateKnowledge(questions) {
        const url = \`\${this.baseUrl}/api/v1/knowledge/validate-knowledge/\${this.fabricId}\`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ questions })
        });
        return await response.json();
    }
    
    async getStatus() {
        const url = \`\${this.baseUrl}/api/v1/knowledge/\`;
        const response = await fetch(url);
        return await response.json();
    }
}

// Usage with async/await
async function example() {
    const client = new AdvancedKnowledgeFabricClient('${fabricId}');
    
    try {
        // Query with specific LLM provider
        const result = await client.query('What are the claims procedures?', 'openai');
        console.log('Answer:', result.answer);
        console.log('Confidence:', result.confidence);
        console.log('Processing Time:', result.processingTime);
        
        // Validate knowledge base
        const validation = await client.validateKnowledge([
            'What is this document about?',
            'What are the key procedures?'
        ]);
        console.log('Validation Score:', validation.data.validation_score);
        
    } catch (error) {
        console.error('Error:', error);
    }
}

// Run the example
example();`
  };

  const copyToClipboard = async (text: string, endpointName: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedEndpoint(endpointName);
      setTimeout(() => setCopiedEndpoint(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const getFullUrl = (endpoint: string) => {
    return `http://localhost:8000${endpoint}`;
  };

  const renderEndpoints = () => (
    <div className="space-y-6">
      {endpoints.map((endpoint, index) => (
        <div key={index} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {/* Endpoint Header */}
          <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-semibold text-gray-900">{endpoint.name}</h4>
                <p className="text-sm text-gray-600">{endpoint.description}</p>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                endpoint.method === 'GET' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {endpoint.method}
              </span>
            </div>
          </div>

          {/* Endpoint URL */}
          <div className="px-4 py-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <code className="text-sm bg-gray-100 px-3 py-2 rounded flex-1 mr-3">
                {getFullUrl(endpoint.endpoint)}
              </code>
              <button
                onClick={() => copyToClipboard(getFullUrl(endpoint.endpoint), endpoint.name)}
                className="flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
              >
                {copiedEndpoint === endpoint.name ? (
                  <CheckIcon className="w-4 h-4" />
                ) : (
                  <DocumentDuplicateIcon className="w-4 h-4" />
                )}
                <span className="text-xs">
                  {copiedEndpoint === endpoint.name ? 'Copied!' : 'Copy'}
                </span>
              </button>
            </div>
          </div>

          {/* Example */}
          <div className="px-4 py-3">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Request */}
              <div>
                <h5 className="text-sm font-medium text-gray-700 mb-2">Request Example:</h5>
                <div className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto">
                  <pre>{JSON.stringify(endpoint.example.request, null, 2)}</pre>
                </div>
              </div>

              {/* Response */}
              <div>
                <h5 className="text-sm font-medium text-gray-700 mb-2">Response Example:</h5>
                <div className="bg-gray-900 text-green-400 p-3 rounded text-xs overflow-x-auto">
                  <pre>{JSON.stringify(endpoint.example.response, null, 2)}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const renderLangChain = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-blue-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-blue-900">Basic LangChain Integration</h4>
          <p className="text-sm text-blue-700">Simple tool integration for agents</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{langchainExamples.basic}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(langchainExamples.basic, 'langchain-basic')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'langchain-basic' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'langchain-basic' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-purple-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-purple-900">Advanced LangChain Integration</h4>
          <p className="text-sm text-purple-700">Multiple tools with custom prompts</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{langchainExamples.advanced}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(langchainExamples.advanced, 'langchain-advanced')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'langchain-advanced' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'langchain-advanced' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );

  const renderPython = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-green-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-green-900">Basic Python Client</h4>
          <p className="text-sm text-green-700">Simple HTTP client for knowledge fabric</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{pythonExamples.basic}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(pythonExamples.basic, 'python-basic')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'python-basic' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'python-basic' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-orange-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-orange-900">Advanced Python Client</h4>
          <p className="text-sm text-orange-700">Type-safe client with error handling</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{pythonExamples.advanced}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(pythonExamples.advanced, 'python-advanced')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'python-advanced' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'python-advanced' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );

  const renderJavaScript = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-yellow-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-yellow-900">Basic JavaScript Client</h4>
          <p className="text-sm text-yellow-700">Simple fetch-based client</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{javascriptExamples.basic}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(javascriptExamples.basic, 'javascript-basic')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'javascript-basic' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'javascript-basic' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="bg-indigo-50 px-4 py-3 border-b border-gray-200">
          <h4 className="font-semibold text-indigo-900">Advanced JavaScript Client</h4>
          <p className="text-sm text-indigo-700">Async/await with error handling</p>
        </div>
        <div className="p-4">
          <div className="bg-gray-900 text-green-400 p-4 rounded text-sm overflow-x-auto">
            <pre>{javascriptExamples.advanced}</pre>
          </div>
          <button
            onClick={() => copyToClipboard(javascriptExamples.advanced, 'javascript-advanced')}
            className="mt-3 flex items-center space-x-1 text-blue-600 hover:text-blue-800 transition-colors"
          >
            {copiedEndpoint === 'javascript-advanced' ? (
              <CheckIcon className="w-4 h-4" />
            ) : (
              <DocumentDuplicateIcon className="w-4 h-4" />
            )}
            <span className="text-xs">
              {copiedEndpoint === 'javascript-advanced' ? 'Copied!' : 'Copy Code'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 transition-opacity" aria-hidden="true">
          <div className="absolute inset-0 bg-gray-900 opacity-75"></div>
        </div>

        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-7xl sm:w-full">
          {/* Header */}
          <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">
                  Agent Integration for {fabricName}
                </h3>
                <p className="text-sm text-green-100">
                  Complete integration examples for LangChain, Python, and JavaScript
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-white hover:text-gray-200 transition-colors"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-gray-100 px-6 py-3 border-b border-gray-200">
            <div className="flex space-x-1">
              <button
                onClick={() => setActiveTab('endpoints')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'endpoints'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <CommandLineIcon className="w-4 h-4 inline mr-2" />
                API Endpoints
              </button>
              <button
                onClick={() => setActiveTab('langchain')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'langchain'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <CodeBracketIcon className="w-4 h-4 inline mr-2" />
                LangChain
              </button>
              <button
                onClick={() => setActiveTab('python')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'python'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <CodeBracketIcon className="w-4 h-4 inline mr-2" />
                Python
              </button>
              <button
                onClick={() => setActiveTab('javascript')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === 'javascript'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <CodeBracketIcon className="w-4 h-4 inline mr-2" />
                JavaScript
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="bg-gray-50 max-h-96 overflow-y-auto p-6">
            {activeTab === 'endpoints' && renderEndpoints()}
            {activeTab === 'langchain' && renderLangChain()}
            {activeTab === 'python' && renderPython()}
            {activeTab === 'javascript' && renderJavaScript()}

            {/* Integration Tips */}
            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-semibold text-blue-900 mb-2">🚀 Agent Integration Tips:</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• <strong>LangChain:</strong> Use as a tool in your agent for knowledge retrieval</li>
                <li>• <strong>Python:</strong> Perfect for custom agents and automation scripts</li>
                <li>• <strong>JavaScript:</strong> Great for web-based agents and Node.js applications</li>
                <li>• <strong>Error Handling:</strong> Always check response.success before using data</li>
                <li>• <strong>Rate Limiting:</strong> Implement proper delays between requests</li>
                <li>• <strong>Authentication:</strong> Add API keys for production deployments</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FabricEndpointsDialog; 