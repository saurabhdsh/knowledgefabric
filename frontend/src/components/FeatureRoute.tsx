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

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-[#8b9cb0]">
        Checking access…
      </div>
    );
  }

  if (!can(feature)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

export default FeatureRoute;
