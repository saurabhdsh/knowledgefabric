import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { WeaveFeatureKey } from '../utils/authStorage';

interface FeatureRouteProps {
  feature: WeaveFeatureKey;
  children: React.ReactNode;
}

const FeatureRoute: React.FC<FeatureRouteProps> = ({ feature, children }) => {
  const { can, isLoading } = useAuth();

  // Keep the prior page shell visible during the tiny auth resolve — a text
  // flash here read as a navigation hitch.
  if (isLoading) {
    return <div className="min-h-[24vh]" aria-hidden />;
  }

  if (!can(feature)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

export default FeatureRoute;
