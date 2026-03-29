import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { PrivateRoute, PublicRoute } from './router';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EmployeesPage from './pages/EmployeesPage';
import EmployeeDetailPage from './pages/EmployeeDetailPage';

// Placeholder components - these will be created later
const Search = () => <div className="min-h-screen p-8"><h1 className="text-2xl">Search</h1></div>;
const Upload = () => <div className="min-h-screen p-8"><h1 className="text-2xl">Bulk Upload</h1></div>;

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        } 
      />

      {/* Protected routes */}
      <Route 
        path="/dashboard" 
        element={
          <PrivateRoute>
            <DashboardPage />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/employees" 
        element={
          <PrivateRoute>
            <EmployeesPage />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/employees/:id" 
        element={
          <PrivateRoute>
            <EmployeeDetailPage />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/search" 
        element={
          <PrivateRoute>
            <Search />
          </PrivateRoute>
        } 
      />
      <Route 
        path="/upload" 
        element={
          <PrivateRoute>
            <Upload />
          </PrivateRoute>
        } 
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
