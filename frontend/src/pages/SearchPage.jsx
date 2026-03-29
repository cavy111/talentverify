import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { useAuth } from '../context/AuthContext';
import apiClient from '../api/client';

const SearchPage = () => {
  const { currentUser, isAuthenticated } = useAuth();
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm();

  const searchMutation = useMutation({
    mutationFn: async (data) => {
      // Build query params
      const params = new URLSearchParams();
      
      if (data.name) params.append('name', data.name);
      if (data.employer) params.append('employer', data.employer);
      if (data.position) params.append('position', data.position);
      if (data.department) params.append('department', data.department);
      if (data.year_started) params.append('year_started', data.year_started);
      if (data.year_left) params.append('year_left', data.year_left);

      const response = await apiClient.get(`/search/?${params.toString()}`);
      return response.data;
    },
    onSuccess: (data) => {
      setSearchResults(data.results || []);
      setHasSearched(true);
      setIsSearching(false);
    },
    onError: (error) => {
      console.error('Search error:', error);
      setSearchResults([]);
      setHasSearched(true);
      setIsSearching(false);
    },
  });

  const onSearch = (data) => {
    setIsSearching(true);
    searchMutation.mutate(data);
  };

  const maskName = (firstName, lastName) => {
    if (isAuthenticated) {
      return `${firstName} ${lastName}`;
    }
    
    // Show initials only for non-authenticated users
    const firstInitial = firstName ? firstName.charAt(0).toUpperCase() : '';
    const lastInitial = lastName ? lastName.charAt(0).toUpperCase() : '';
    return `${firstInitial}${lastInitial}`;
  };

  const clearSearch = () => {
    reset();
    setSearchResults([]);
    setHasSearched(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="px-4 py-6 sm:px-0">
          <h1 className="text-3xl font-bold text-gray-900">Employee Verification Search</h1>
          <p className="mt-2 text-gray-600">
            Search for employment records and verify credentials
            {!isAuthenticated && ' (Limited access - sign in for full details)'}
          </p>
        </div>

        {/* Search Form */}
        <div className="px-4 py-6 sm:px-0">
          <div className="bg-white shadow rounded-lg">
            <form onSubmit={handleSubmit(onSearch)} className="p-6">
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {/* Name Field */}
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                    Name
                  </label>
                  <input
                    {...register('name')}
                    type="text"
                    id="name"
                    placeholder="John Doe"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Full name for exact match search
                  </p>
                </div>

                {/* Employer Field */}
                <div>
                  <label htmlFor="employer" className="block text-sm font-medium text-gray-700">
                    Employer
                  </label>
                  <input
                    {...register('employer')}
                    type="text"
                    id="employer"
                    placeholder="Company Name"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Company name (partial match)
                  </p>
                </div>

                {/* Position Field */}
                <div>
                  <label htmlFor="position" className="block text-sm font-medium text-gray-700">
                    Position
                  </label>
                  <input
                    {...register('position')}
                    type="text"
                    id="position"
                    placeholder="Software Engineer"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Job title (partial match)
                  </p>
                </div>

                {/* Department Field */}
                <div>
                  <label htmlFor="department" className="block text-sm font-medium text-gray-700">
                    Department
                  </label>
                  <input
                    {...register('department')}
                    type="text"
                    id="department"
                    placeholder="Engineering"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Department name (partial match)
                  </p>
                </div>

                {/* Year Started Field */}
                <div>
                  <label htmlFor="year_started" className="block text-sm font-medium text-gray-700">
                    Year Started
                  </label>
                  <input
                    {...register('year_started', {
                      pattern: {
                        value: /^\d{4}$/,
                        message: 'Please enter a valid year (e.g., 2020)',
                      },
                    })}
                    type="text"
                    id="year_started"
                    placeholder="2020"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  {errors.year_started && (
                    <p className="mt-1 text-sm text-red-600">{errors.year_started.message}</p>
                  )}
                  <p className="mt-1 text-xs text-gray-500">
                    Employment start year
                  </p>
                </div>

                {/* Year Left Field */}
                <div>
                  <label htmlFor="year_left" className="block text-sm font-medium text-gray-700">
                    Year Left
                  </label>
                  <input
                    {...register('year_left', {
                      pattern: {
                        value: /^\d{4}$/,
                        message: 'Please enter a valid year (e.g., 2023)',
                      },
                    })}
                    type="text"
                    id="year_left"
                    placeholder="2023"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  />
                  {errors.year_left && (
                    <p className="mt-1 text-sm text-red-600">{errors.year_left.message}</p>
                  )}
                  <p className="mt-1 text-xs text-gray-500">
                    Employment end year (optional)
                  </p>
                </div>
              </div>

              {/* Form Actions */}
              <div className="mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={clearSearch}
                  className="inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                  Clear
                </button>
                <button
                  type="submit"
                  disabled={isSearching}
                  className="inline-flex justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
                >
                  {isSearching ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Searching...
                    </>
                  ) : (
                    'Search'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Search Results */}
        {hasSearched && (
          <div className="px-4 py-6 sm:px-0">
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:px-6">
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                  Search Results
                </h3>
                
                {isSearching ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-500">Searching...</p>
                  </div>
                ) : searchResults.length === 0 ? (
                  <div className="text-center py-8">
                    <svg
                      className="mx-auto h-12 w-12 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <h3 className="mt-2 text-sm font-medium text-gray-900">No results found</h3>
                    <p className="mt-1 text-sm text-gray-500">
                      Try adjusting your search criteria
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {searchResults.map((employee) => (
                      <div key={employee.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="text-lg font-medium text-gray-900">
                              {maskName(employee.first_name, employee.last_name)}
                            </h4>
                            {!isAuthenticated && (
                              <p className="text-xs text-gray-500 mt-1">
                                Full name hidden for privacy
                              </p>
                            )}
                            
                            {/* Current Employment */}
                            {employee.current_employment && (
                              <div className="mt-3 space-y-1">
                                <div className="flex items-center text-sm text-gray-600">
                                  <svg
                                    className="h-4 w-4 mr-2 text-gray-400"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                                    />
                                  </svg>
                                  {employee.current_employment.role_title}
                                </div>
                                
                                {employee.current_employment.company_name && (
                                  <div className="flex items-center text-sm text-gray-600">
                                    <svg
                                      className="h-4 w-4 mr-2 text-gray-400"
                                      fill="none"
                                      stroke="currentColor"
                                      viewBox="0 0 24 24"
                                    >
                                      <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                                      />
                                    </svg>
                                    {employee.current_employment.company_name}
                                  </div>
                                )}
                                
                                {employee.current_employment.department_name && (
                                  <div className="flex items-center text-sm text-gray-600">
                                    <svg
                                      className="h-4 w-4 mr-2 text-gray-400"
                                      fill="none"
                                      stroke="currentColor"
                                      viewBox="0 0 24 24"
                                    >
                                      <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                                      />
                                    </svg>
                                    {employee.current_employment.department_name}
                                  </div>
                                )}
                                
                                <div className="flex items-center text-sm text-gray-600">
                                  <svg
                                    className="h-4 w-4 mr-2 text-gray-400"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                                    />
                                  </svg>
                                  {employee.current_employment.date_started
                                    ? new Date(employee.current_employment.date_started).toLocaleDateString()
                                    : 'Unknown'}{' '}
                                  -{' '}
                                  {employee.current_employment.date_left
                                    ? new Date(employee.current_employment.date_left).toLocaleDateString()
                                    : 'Present'}
                                </div>
                              </div>
                            )}
                            
                            {/* Employee ID */}
                            {employee.employee_id_number && (
                              <div className="mt-2">
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                                  ID: {employee.employee_id_number}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                        
                        {isAuthenticated && (
                          <div className="mt-4 pt-4 border-t border-gray-200">
                            <a
                              href={`/employees/${employee.id}`}
                              className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                            >
                              View Full Profile →
                            </a>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
