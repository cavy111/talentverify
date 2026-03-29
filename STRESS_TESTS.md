# Talent Verify Load Testing Guide

This document explains the load testing setup for the Talent Verify platform using Locust.

## Overview

The load testing simulates real-world usage patterns to ensure the platform can handle expected traffic volumes and identify performance bottlenecks before they impact users.

## Test Scenarios

### Why These Three Tasks Were Chosen

The three primary load testing tasks represent the highest-frequency endpoints in a production Talent Verify deployment:

#### 1. SearchTask (Weight: 60) - Public Employee Verification
- **Purpose**: Simulates external verification requests from employers, recruiters, and background check services
- **Frequency**: Highest - This is the primary public-facing service
- **Real-world pattern**: External parties constantly verify employee credentials
- **Impact**: Critical for business operations - verification failures directly impact customer trust

#### 2. LoginTask (Weight: 20) - User Authentication
- **Purpose**: Tests authentication system under load
- **Frequency**: Medium - Users log in throughout the day for various operations
- **Real-world pattern**: Company admins and HR staff accessing the system
- **Impact**: Authentication failures prevent all other operations

#### 3. EmployeeListTask (Weight: 20) - Internal Data Management
- **Purpose**: Tests authenticated data access and pagination
- **Frequency**: Medium - Internal users browse and manage employee data
- **Real-world pattern**: HR operations, bulk updates, data verification
- **Impact**: Slow data access affects internal productivity

## Performance Metrics to Watch

### Primary Success Criteria

#### 1. Response Time (p95 < 500ms)
- **What it measures**: 95th percentile response time
- **Why it matters**: Ensures most users get fast responses
- **Target**: < 500ms for all endpoints
- **Warning signs**: p95 > 1s indicates performance issues

#### 2. Error Rate (< 1%)
- **What it measures**: Percentage of failed requests
- **Why it matters**: High error rates indicate system instability
- **Target**: < 1% total errors
- **Warning signs**: Error rate > 5% requires immediate attention

#### 3. Throughput (> 50 req/s)
- **What it measures**: Requests per second the system can handle
- **Why it matters**: Indicates system capacity under load
- **Target**: > 50 requests/second sustained
- **Warning signs**: Throughput dropping under load

### Secondary Metrics

#### 4. Response Time Distribution
- **p50 (median)**: Typical user experience
- **p90**: 90% of users see this response time or better
- **p99**: Worst-case scenarios for 99% of users

#### 5. User Count vs Response Time
- Monitor how response times degrade as user count increases
- Identify the "knee" where performance sharply declines

#### 6. Error Types
- **4xx errors**: Client-side issues (authentication, validation)
- **5xx errors**: Server-side issues (database, application errors)
- **Timeouts**: System overload or slow operations

## Running Load Tests

### Basic Load Test
```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run basic load test
locust --headless -u 100 -r 10 --run-time 60s --host=http://localhost:8000
```

### Advanced Test Scenarios

#### Stress Test (Find Breaking Point)
```bash
# Gradually increase users to find system limits
locust --headless -u 500 -r 50 --run-time 300s --host=http://localhost:8000
```

#### Spike Test (Sudden Traffic Surge)
```bash
# Simulate sudden traffic spike
locust --headless -u 50 -r 50 --run-time 30s --spawn-rate 50 --host=http://localhost:8000
```

#### Soak Test (Sustained Load)
```bash
# Test system stability over extended period
locust --headless -u 100 -r 10 --run-time 3600s --host=http://localhost:8000
```

#### Different User Types
```bash
# Test with specific user classes
locust --headless -u 50 -r 5 --run-time 120s --host=http://localhost:8000 TalentVerifyUser
locust --headless -u 200 -r 20 --run-time 120s --host=http://localhost:8000 PublicSearchUser
```

## Interpreting Locust Reports

### Web Interface (when not using --headless)
- **Statistics tab**: Real-time metrics and request distribution
- **Charts tab**: Visual representation of performance over time
- **Failures tab**: Detailed error information and stack traces
- **Download tab**: Export test data for further analysis

### Command Line Output
```
# Example output interpretation
 Type      Name                     # reqs      # fails     Avg     Min     Max    |  Median   p90     p95    p99     req/s
--------------------------------------------------------------------------------------------------------
 GET       /api/search/               1200         6     245ms    45ms   1.2s    |  230ms   380ms   450ms   800ms    20.0
 POST      /api/auth/login/           400          2     180ms    60ms   350ms    |  170ms   280ms   320ms   340ms     6.7
 GET       /api/employees/            400          1     320ms   120ms   800ms    |  300ms   450ms   550ms   720ms     6.7
--------------------------------------------------------------------------------------------------------
 Total                                    2000         9     243ms    45ms   1.2s    |  230ms   380ms   450ms   800ms    33.3
```

### Key Indicators

#### ✅ Healthy System
- p95 response times < 500ms
- Error rate < 1%
- Stable throughput (req/s)
- No significant performance degradation over time

#### ⚠️ Warning Signs
- p95 response times > 1s
- Error rate 1-5%
- Throughput fluctuations
- Response times increasing over time

#### 🚨 Critical Issues
- p95 response times > 2s
- Error rate > 5%
- Sudden throughput drops
- High number of 5xx errors

## Performance Optimization Checklist

### Before Testing
- [ ] Database indexes are optimized
- [ ] Redis cache is configured and running
- [ ] Application server (Gunicorn/uWSGI) is tuned
- [ ] Database connection pool is sized correctly
- [ ] Static files are served efficiently
- [ ] Security headers don't impact performance

### During Testing
- [ ] Monitor database query performance
- [ ] Check cache hit rates
- [ ] Watch memory usage patterns
- [ ] Monitor CPU utilization
- [ ] Check for connection leaks
- [ ] Verify audit logging performance

### After Testing
- [ ] Analyze slowest endpoints
- [ ] Review database query logs
- [ ] Check for memory leaks
- [ ] Document performance baselines
- [ ] Create performance regression tests
- [ ] Plan capacity upgrades if needed

## Troubleshooting Common Issues

### High Response Times
1. **Database queries**: Check for slow queries or missing indexes
2. **Cache misses**: Verify Redis is working and cache keys are correct
3. **Memory pressure**: Monitor for garbage collection pauses
4. **Network latency**: Check database and Redis connection performance

### High Error Rates
1. **Authentication failures**: Check JWT token handling
2. **Database connections**: Verify connection pool settings
3. **Rate limiting**: Ensure limits aren't too restrictive
4. **Resource exhaustion**: Check for memory or CPU limits

### Low Throughput
1. **Bottleneck identification**: Use profiling tools
2. **Concurrency limits**: Check server worker processes
3. **Database locks**: Look for long-running transactions
4. **External dependencies**: Verify third-party service performance

## Production Monitoring

### Alert Thresholds
- p95 response time > 1s for 5 minutes
- Error rate > 2% for 2 minutes
- Throughput drop > 20% for 5 minutes
- Database connection pool > 80% utilization

### Dashboards
- Response time trends (p50, p90, p95, p99)
- Request rate and error rate
- Database performance metrics
- Cache hit rates and memory usage
- System resource utilization

### Continuous Testing
- Run automated load tests in CI/CD pipeline
- Test against performance regression
- Monitor baseline performance over time
- Schedule regular stress tests during maintenance windows

## Best Practices

1. **Test in realistic environments** that mirror production setup
2. **Use realistic data volumes** and user behavior patterns
3. **Monitor system resources** during tests, not just application metrics
4. **Document baselines** and performance expectations
5. **Test failure scenarios** (database failures, cache misses, etc.)
6. **Involve the whole team** in performance analysis and optimization
7. **Plan for growth** based on test results and business projections
