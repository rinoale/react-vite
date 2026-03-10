import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth.js';

export function RequireRole({ role, children, redirectTo = '/login', unauthorizedTo }) {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) return null;
  if (!isAuthenticated) return <Navigate to={redirectTo} state={{ from: location.pathname }} replace />;

  const hasRole = user?.roles?.includes(role) || user?.roles?.includes('master');
  if (!hasRole) {
    if (unauthorizedTo) return <Navigate to={unauthorizedTo} replace />;
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center">
        <p className="text-gray-500">Unauthorized</p>
      </div>
    );
  }

  return children;
}
