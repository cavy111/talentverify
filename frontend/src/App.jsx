import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { PrivateRoute, PublicRoute } from './router';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import EmployeesPage from './pages/EmployeesPage';
import EmployeeDetailPage from './pages/EmployeeDetailPage';
import SearchPage from './pages/SearchPage';
import UploadPage from './pages/UploadPage';

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
      {/* Public search route */}
      <Route 
        path="/search" 
        element={<SearchPage />} 
      />
      
      <Route 
        path="/upload" 
        element={
          <PrivateRoute>
            <UploadPage />
          </PrivateRoute>
        } 
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
