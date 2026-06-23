import ee
import time

ee.Initialize(project='lsms-497103')

# Check status of the most recent failed tasks
tasks = ee.batch.Task.list()

print("Last 5 tasks and their errors:\n")
for task in tasks[:5]:
    status = task.status()
    print(f"Task: {status['description']}")
    print(f"State: {status['state']}")
    # This prints the actual error reason
    print(f"Error: {status.get('error_message', 'No error message')}")
    print("-" * 50)