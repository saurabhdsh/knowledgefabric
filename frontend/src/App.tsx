import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import FeatureRoute from './components/FeatureRoute';
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
import UserManagement from './pages/UserManagement';

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
                  <Route
                    path="/"
                    element={
                      <FeatureRoute feature="dashboard">
                        <Dashboard />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/knowledge"
                    element={
                      <FeatureRoute feature="create_knowledge">
                        <Knowledge />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/train-ml"
                    element={
                      <FeatureRoute feature="train_ml">
                        <TrainMLModels />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/fabrics"
                    element={
                      <FeatureRoute feature="fabrics">
                        <Fabrics />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/test-llm"
                    element={
                      <FeatureRoute feature="test_llm">
                        <TestLLM />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/context"
                    element={
                      <FeatureRoute feature="context">
                        <ContextAnalysis />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/ontology"
                    element={
                      <FeatureRoute feature="ontology">
                        <OntologyDashboard />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/ontology/workspace/:projectId"
                    element={
                      <FeatureRoute feature="ontology">
                        <OntologyWorkspace />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/ontology/enrichment"
                    element={
                      <FeatureRoute feature="ontology_enrichment">
                        <OntologyEnrichment />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/ontology/agent-utilities"
                    element={
                      <FeatureRoute feature="agent_utilities">
                        <AgentDataUtilities />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/fabrics/:fabricId/knowledge-graph"
                    element={
                      <FeatureRoute feature="fabrics">
                        <FabricKnowledgeGraph />
                      </FeatureRoute>
                    }
                  />
                  <Route
                    path="/users"
                    element={
                      <FeatureRoute feature="user_management">
                        <UserManagement />
                      </FeatureRoute>
                    }
                  />
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
