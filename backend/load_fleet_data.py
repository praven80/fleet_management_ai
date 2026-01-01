#!/usr/bin/env python3
"""
Generate and load mock fleet data into DynamoDB
Creates realistic vehicle inventory across multiple US cities
"""
import boto3
import random
from datetime import datetime, timedelta
import uuid
from decimal import Decimal

# Major US cities with ZIP codes
CITIES = [
    {"name": "Los Angeles", "state": "CA", "zip_codes": ["90001", "90002", "90003", "90004", "90005", "90006", "90007", "90008"]},
    {"name": "New York", "state": "NY", "zip_codes": ["10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008"]},
    {"name": "Chicago", "state": "IL", "zip_codes": ["60601", "60602", "60603", "60604", "60605", "60606", "60607", "60608"]},
    {"name": "Houston", "state": "TX", "zip_codes": ["77001", "77002", "77003", "77004", "77005", "77006", "77007", "77008"]},
    {"name": "Phoenix", "state": "AZ", "zip_codes": ["85001", "85002", "85003", "85004", "85005", "85006", "85007", "85008"]},
    {"name": "Miami", "state": "FL", "zip_codes": ["33101", "33102", "33109", "33125", "33126", "33127", "33128", "33129"]},
    {"name": "Atlanta", "state": "GA", "zip_codes": ["30301", "30302", "30303", "30304", "30305", "30306", "30307", "30308"]},
    {"name": "Seattle", "state": "WA", "zip_codes": ["98101", "98102", "98103", "98104", "98105", "98106", "98107", "98108"]},
    {"name": "Denver", "state": "CO", "zip_codes": ["80201", "80202", "80203", "80204", "80205", "80206", "80207", "80208"]},
    {"name": "Boston", "state": "MA", "zip_codes": ["02101", "02102", "02103", "02104", "02105", "02106", "02107", "02108"]},
]

# Vehicle types with realistic pricing
VEHICLES = [
    {"make": "Toyota", "model": "Camry", "year": 2024, "category": "sedan", "daily_rate": (45, 65)},
    {"make": "Honda", "model": "Accord", "year": 2024, "category": "sedan", "daily_rate": (45, 65)},
    {"make": "Ford", "model": "Escape", "year": 2024, "category": "suv", "daily_rate": (55, 75)},
    {"make": "Chevrolet", "model": "Equinox", "year": 2024, "category": "suv", "daily_rate": (55, 75)},
    {"make": "Nissan", "model": "Altima", "year": 2023, "category": "sedan", "daily_rate": (40, 60)},
    {"make": "Hyundai", "model": "Elantra", "year": 2024, "category": "sedan", "daily_rate": (35, 55)},
    {"make": "Jeep", "model": "Grand Cherokee", "year": 2024, "category": "suv", "daily_rate": (70, 90)},
    {"make": "Toyota", "model": "RAV4", "year": 2024, "category": "suv", "daily_rate": (60, 80)},
    {"make": "Honda", "model": "CR-V", "year": 2024, "category": "suv", "daily_rate": (60, 80)},
    {"make": "Ford", "model": "Mustang", "year": 2024, "category": "sports", "daily_rate": (80, 120)},
    {"make": "Chevrolet", "model": "Corvette", "year": 2024, "category": "sports", "daily_rate": (150, 200)},
    {"make": "Tesla", "model": "Model 3", "year": 2024, "category": "electric", "daily_rate": (90, 130)},
    {"make": "Tesla", "model": "Model Y", "year": 2024, "category": "electric", "daily_rate": (100, 140)},
    {"make": "Ford", "model": "F-150", "year": 2024, "category": "truck", "daily_rate": (75, 95)},
    {"make": "Chevrolet", "model": "Silverado", "year": 2024, "category": "truck", "daily_rate": (75, 95)},
    {"make": "Dodge", "model": "Charger", "year": 2024, "category": "sedan", "daily_rate": (65, 85)},
    {"make": "BMW", "model": "3 Series", "year": 2024, "category": "luxury", "daily_rate": (100, 150)},
    {"make": "Mercedes", "model": "C-Class", "year": 2024, "category": "luxury", "daily_rate": (110, 160)},
    {"make": "Audi", "model": "A4", "year": 2024, "category": "luxury", "daily_rate": (105, 155)},
    {"make": "Volkswagen", "model": "Jetta", "year": 2024, "category": "sedan", "daily_rate": (40, 60)},
]

STATUSES = ["available", "rented", "maintenance"]
STATUS_WEIGHTS = [0.6, 0.3, 0.1]  # 60% available, 30% rented, 10% maintenance


def generate_vehicle_data(city, zip_code):
    """Generate a single vehicle record"""
    vehicle = random.choice(VEHICLES)
    status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
    
    # Generate realistic mileage
    mileage = random.randint(5000, 50000)
    
    # Generate daily rate within the vehicle's range (use Decimal for DynamoDB)
    daily_rate = Decimal(str(round(random.uniform(vehicle["daily_rate"][0], vehicle["daily_rate"][1]), 2)))
    
    # Generate license plate
    license_plate = f"{random.choice(['ABC', 'XYZ', 'DEF', 'GHI', 'JKL'])}{random.randint(1000, 9999)}"
    
    # Generate VIN
    vin = f"1{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ0123456789', k=16))}"
    
    # Rental dates if rented
    rental_start = None
    rental_end = None
    if status == "rented":
        rental_start = (datetime.now() - timedelta(days=random.randint(1, 7))).isoformat()
        rental_end = (datetime.now() + timedelta(days=random.randint(1, 14))).isoformat()
    
    return {
        "vehicle_id": str(uuid.uuid4()),
        "make": vehicle["make"],
        "model": vehicle["model"],
        "year": vehicle["year"],
        "category": vehicle["category"],
        "status": status,
        "location": f"{city['name']}, {city['state']}",
        "zip_code": zip_code,
        "daily_rate": daily_rate,
        "mileage": mileage,
        "license_plate": license_plate,
        "vin": vin,
        "rental_start": rental_start,
        "rental_end": rental_end,
        "last_updated": datetime.now().isoformat(),
    }


def clear_existing_data(table_name):
    """Clear all existing records from DynamoDB table"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    print("🗑️  Clearing existing records from DynamoDB...")
    
    # Scan and delete all items
    scan_kwargs = {
        'ProjectionExpression': 'vehicle_id'
    }
    
    deleted_count = 0
    
    try:
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            if not items:
                break
            
            # Batch delete items
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'vehicle_id': item['vehicle_id']})
                    deleted_count += 1
            
            # Check if there are more items to scan
            if 'LastEvaluatedKey' not in response:
                break
            
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        if deleted_count > 0:
            print(f"✅ Deleted {deleted_count} existing records")
        else:
            print("✅ No existing records to delete")
    except Exception as e:
        print(f"⚠️  Error clearing data: {e}")


def load_data_to_dynamodb(table_name, batch_size=25):
    """Generate and load mock data into DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    print(f"\n🚗 Generating mock fleet data for {len(CITIES)} cities...")
    
    total_vehicles = 0
    
    for city in CITIES:
        print(f"\n📍 {city['name']}, {city['state']}")
        
        for zip_code in city['zip_codes']:
            # Generate 15-30 vehicles per ZIP code
            num_vehicles = random.randint(15, 30)
            vehicles = [generate_vehicle_data(city, zip_code) for _ in range(num_vehicles)]
            
            # Batch write to DynamoDB
            with table.batch_writer() as batch:
                for vehicle in vehicles:
                    batch.put_item(Item=vehicle)
            
            total_vehicles += num_vehicles
            print(f"   ✅ {zip_code}: {num_vehicles} vehicles")
    
    print(f"\n✅ Successfully loaded {total_vehicles} vehicles across {len(CITIES)} cities")
    
    # Print summary by city
    print("\n📊 Summary by City:")
    for city in CITIES:
        city_vehicles = sum([random.randint(15, 30) for _ in city['zip_codes']])
        print(f"   {city['name']}, {city['state']}: ~{len(city['zip_codes']) * 22} vehicles")


def main():
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║              Hertz Fleet Data - DynamoDB Loader                         ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝\n")
    
    # Get table name from CloudFormation
    try:
        cfn = boto3.client('cloudformation')
        stack = cfn.describe_stacks(StackName='HertzMcpStack')
        outputs = {o['OutputKey']: o['OutputValue'] for o in stack['Stacks'][0]['Outputs']}
        table_name = outputs.get('FleetTableName', 'hertz-fleet-inventory')
    except Exception as e:
        print(f"⚠️  Could not get table name from CloudFormation: {e}")
        table_name = 'hertz-fleet-inventory'
    
    print(f"📦 Target Table: {table_name}\n")
    
    # Clear existing data first
    clear_existing_data(table_name)
    
    # Load new data
    load_data_to_dynamodb(table_name)
    
    print("\n✅ Data loading complete!")
    print("\n🎯 Next Steps:")
    print("   1. Update fleet_tools.py to use DynamoDB")
    print("   2. Test queries: python -c 'from fleet_tools import search_by_zip; print(search_by_zip(\"90001\"))'")
    print()


if __name__ == "__main__":
    main()
