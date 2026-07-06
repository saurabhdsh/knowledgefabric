import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Knowledge from './pages/Knowledge';
import TrainMLModels from './pages/TrainMLModels';
import Fabrics from './pages/Fabrics';
import TestLLM from './pages/TestLLM';
import ContextAnalysis from './pages/ContextAnalysis';
import OntologyDashboard from './pages/ontology/OntologyDashboard';
import OntologyWorkspace from './pages/ontology/OntologyWorkspace';
import OntologyEnrichment from './pages/ontology/OntologyEnrichment';
import FabricKnowledgeGraph from './pages/FabricKnowledgeGraph';
import AgentDataUtilities from './pages/ontology/AgentDataUtilities';

function App() {
  return (
    <div className="min-h-screen bg-[#040508]">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/knowledge" element={<Knowledge />} />
                  <Route path="/train-ml" element={<TrainMLModels />} />
                  <Route path="/fabrics" element={<Fabrics />} />
                  <Route path="/test-llm" element={<TestLLM />} />
                  <Route path="/context" element={<ContextAnalysis />} />
                  <Route path="/ontology" element={<OntologyDashboard />} />
                  <Route path="/ontology/workspace/:projectId" element={<OntologyWorkspace />} />
                  <Route path="/ontology/enrichment" element={<OntologyEnrichment />} />
                  <Route path="/ontology/agent-utilities" element={<AgentDataUtilities />} />
                  <Route path="/fabrics/:fabricId/knowledge-graph" element={<FabricKnowledgeGraph />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

export default App;
