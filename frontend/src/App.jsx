import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { PrivateRoute, PublicRoute } from './router';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';

// Placeholder components - these will be created later
const Employees = () => <div className="min-h-screen p-8"><h1 className="text-2xl">Employees</h1></div>;
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
            <Employees />
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
