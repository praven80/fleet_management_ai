import React, { useState } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Table,
  Box,
  Button,
  FormField,
  Input,
  Select,
  Grid,
  Pagination,
  TextFilter,
  StatusIndicator,
} from '@cloudscape-design/components';
import { searchFleetVehicles } from '../services/api';

const FleetSearch = () => {
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    make: '',
    model: '',
    category: null,
    status: null,
    zip_code: '',
  });
  const [filteringText, setFilteringText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [sortingColumn, setSortingColumn] = useState({ sortingField: 'vehicle_id' });
  const [isDescending, setIsDescending] = useState(false);
  const itemsPerPage = 20;

  const categoryOptions = [
    { label: 'All Categories', value: null },
    { label: 'Sedan', value: 'sedan' },
    { label: 'SUV', value: 'suv' },
    { label: 'Truck', value: 'truck' },
    { label: 'Sports', value: 'sports' },
    { label: 'Electric', value: 'electric' },
  ];

  const statusOptions = [
    { label: 'All Status', value: null },
    { label: 'Available', value: 'available' },
    { label: 'Rented', value: 'rented' },
    { label: 'Maintenance', value: 'maintenance' },
  ];

  const handleSearch = async () => {
    setLoading(true);
    try {
      // Use DynamoDB via AWS SDK
      const { DynamoDBClient, ScanCommand } = await import('@aws-sdk/client-dynamodb');
      const { unmarshall } = await import('@aws-sdk/util-dynamodb');
      const { fetchAuthSession } = await import('aws-amplify/auth');
      const { fromCognitoIdentityPool } = await import('@aws-sdk/credential-providers');
      const { config } = await import('../config');
      
      // Get credentials from Cognito
      const session = await fetchAuthSession();
      const idToken = session.tokens.idToken.toString();
      
      const credentials = fromCognitoIdentityPool({
        clientConfig: { region: config.region },
        identityPoolId: config.cognito.identityPoolId,
        logins: {
          [`cognito-idp.${config.region}.amazonaws.com/${config.cognito.userPoolId}`]: idToken,
        },
      });
      
      // Create DynamoDB client
      const client = new DynamoDBClient({
        region: config.region,
        credentials,
      });
      
      // Scan the fleet table
      const command = new ScanCommand({
        TableName: config.dynamoDBTable,
      });
      
      const response = await client.send(command);
      let vehicles = response.Items.map(item => unmarshall(item));
      
      // Apply client-side filters
      if (filters.make) {
        vehicles = vehicles.filter(v => 
          v.make.toLowerCase().includes(filters.make.toLowerCase())
        );
      }
      if (filters.model) {
        vehicles = vehicles.filter(v => 
          v.model.toLowerCase().includes(filters.model.toLowerCase())
        );
      }
      if (filters.category?.value) {
        vehicles = vehicles.filter(v => 
          v.category.toLowerCase() === filters.category.value.toLowerCase()
        );
      }
      if (filters.status?.value) {
        vehicles = vehicles.filter(v => v.status === filters.status.value);
      }
      if (filters.zip_code) {
        vehicles = vehicles.filter(v => v.zip_code === filters.zip_code);
      }
      
      setVehicles(vehicles);
      setCurrentPage(1);
    } catch (error) {
      console.error('Search failed:', error);
      setVehicles([]);
    } finally {
      setLoading(false);
    }
  };

  // Load initial data on mount
  React.useEffect(() => {
    handleSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredVehicles = vehicles.filter((vehicle) =>
    filteringText === '' ||
    vehicle.make.toLowerCase().includes(filteringText.toLowerCase()) ||
    vehicle.model.toLowerCase().includes(filteringText.toLowerCase()) ||
    vehicle.location.toLowerCase().includes(filteringText.toLowerCase())
  );

  // Sort vehicles
  const sortedVehicles = [...filteredVehicles].sort((a, b) => {
    const field = sortingColumn.sortingField;
    let aVal = a[field];
    let bVal = b[field];
    
    // Handle numeric fields
    if (field === 'year' || field === 'daily_rate' || field === 'mileage') {
      aVal = Number(aVal) || 0;
      bVal = Number(bVal) || 0;
    } else {
      // Handle string fields
      aVal = String(aVal || '').toLowerCase();
      bVal = String(bVal || '').toLowerCase();
    }
    
    if (aVal < bVal) return isDescending ? 1 : -1;
    if (aVal > bVal) return isDescending ? -1 : 1;
    return 0;
  });

  const paginatedVehicles = sortedVehicles.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const getStatusIndicator = (status) => {
    const statusMap = {
      available: 'success',
      rented: 'warning',
      maintenance: 'error',
    };
    return <StatusIndicator type={statusMap[status]}>{status}</StatusIndicator>;
  };

  return (
    <Container
      header={
        <Header variant="h1" description="Search and filter fleet vehicles across all locations">
          <span style={{ display: 'flex', alignItems: 'center', gap: '12px', whiteSpace: 'nowrap' }}>
            <span style={{ fontSize: '32px' }}>🔍</span>
            <span>Fleet Search</span>
          </span>
        </Header>
      }
    >
      <SpaceBetween size="l">
        <Grid gridDefinition={[{ colspan: 3 }, { colspan: 3 }, { colspan: 2 }, { colspan: 2 }, { colspan: 2 }]}>
          <FormField label="Make">
            <Input
              value={filters.make}
              onChange={({ detail }) => setFilters({ ...filters, make: detail.value })}
              placeholder="e.g., Toyota"
            />
          </FormField>
          <FormField label="Model">
            <Input
              value={filters.model}
              onChange={({ detail }) => setFilters({ ...filters, model: detail.value })}
              placeholder="e.g., Camry"
            />
          </FormField>
          <FormField label="Category">
            <Select
              selectedOption={filters.category}
              onChange={({ detail }) => setFilters({ ...filters, category: detail.selectedOption })}
              options={categoryOptions}
              placeholder="Select category"
            />
          </FormField>
          <FormField label="Status">
            <Select
              selectedOption={filters.status}
              onChange={({ detail }) => setFilters({ ...filters, status: detail.selectedOption })}
              options={statusOptions}
              placeholder="Select status"
            />
          </FormField>
          <FormField label="ZIP Code">
            <Input
              value={filters.zip_code}
              onChange={({ detail }) => setFilters({ ...filters, zip_code: detail.value })}
              placeholder="e.g., 90001"
            />
          </FormField>
        </Grid>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <span style={{ fontSize: '14px', color: '#545b64', fontWeight: '600' }}>
              Page {currentPage} of {Math.ceil(sortedVehicles.length / itemsPerPage) || 1} 
              {' '}({sortedVehicles.length} total vehicles)
            </span>
          </Box>
          <Box>
            <Button variant="primary" onClick={handleSearch} loading={loading} iconName="search">
              Search Fleet
            </Button>
          </Box>
        </div>

        <Table
          columnDefinitions={[
            {
              id: 'vehicle_id',
              header: 'Vehicle ID',
              cell: (item) => item.vehicle_id,
              sortingField: 'vehicle_id',
            },
            {
              id: 'make',
              header: 'Make',
              cell: (item) => item.make,
              sortingField: 'make',
            },
            {
              id: 'model',
              header: 'Model',
              cell: (item) => item.model,
              sortingField: 'model',
            },
            {
              id: 'year',
              header: 'Year',
              cell: (item) => item.year,
              sortingField: 'year',
            },
            {
              id: 'category',
              header: 'Category',
              cell: (item) => item.category,
              sortingField: 'category',
            },
            {
              id: 'status',
              header: 'Status',
              cell: (item) => getStatusIndicator(item.status),
              sortingField: 'status',
            },
            {
              id: 'daily_rate',
              header: 'Daily Rate',
              cell: (item) => `$${item.daily_rate}`,
              sortingField: 'daily_rate',
            },
            {
              id: 'location',
              header: 'Location',
              cell: (item) => `${item.location} (${item.zip_code})`,
              sortingField: 'location',
            },
            {
              id: 'mileage',
              header: 'Mileage',
              cell: (item) => item.mileage?.toLocaleString() || 'N/A',
              sortingField: 'mileage',
            },
          ]}
          items={paginatedVehicles}
          loading={loading}
          loadingText="Loading vehicles"
          sortingColumn={sortingColumn}
          sortingDescending={isDescending}
          onSortingChange={({ detail }) => {
            setSortingColumn(detail.sortingColumn);
            setIsDescending(detail.isDescending);
          }}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No vehicles found</b>
              <Box padding={{ bottom: 's' }} variant="p" color="inherit">
                Try adjusting your search filters
              </Box>
            </Box>
          }
          filter={
            <TextFilter
              filteringText={filteringText}
              filteringPlaceholder="Find vehicles"
              onChange={({ detail }) => setFilteringText(detail.filteringText)}
            />
          }
          pagination={
            <Pagination
              currentPageIndex={currentPage}
              pagesCount={Math.ceil(filteredVehicles.length / itemsPerPage)}
              onChange={({ detail }) => setCurrentPage(detail.currentPageIndex)}
            />
          }
        />
      </SpaceBetween>
    </Container>
  );
};

export default FleetSearch;
