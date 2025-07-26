import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Knowledge from './pages/Knowledge';
import Fabrics from './pages/Fabrics';
import TestLLM from './pages/TestLLM';
import ContextAnalysis from './pages/ContextAnalysis';

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/fabrics" element={<Fabrics />} />
          <Route path="/test-llm" element={<TestLLM />} />
          <Route path="/context" element={<ContextAnalysis />} />
        </Routes>
      </Layout>
    </div>
  );
}

export default App; 