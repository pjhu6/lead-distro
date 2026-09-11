import asyncio
import json
import argparse
import httpx

BASE_URL = "http://localhost:8000"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "file", 
        nargs="?", 
        default="sample_test_case.json", 
        help="Path to the JSON file containing test cases."
    )
    args = parser.parse_args()

    try:
        with open(args.file, "r") as f:
            steps = json.load(f)
    except FileNotFoundError:
        print(f"Could not find file '{args.file}'.")
        return

    print(f"Loaded {len(steps)} test steps from {args.file}.")
    print(f"Please make sure lead-distro hasn't received any other traffic, as this script expects the default state. (You may want to restart the server)")
    print("Press [ENTER] to execute each step, or type 'q' to quit.\n")

    async with httpx.AsyncClient() as client:
        for i, step in enumerate(steps, 1):
            print("-" * 50)
            print(f"Step {i}: {step['description']}")
            print(f"Request: {step['method']} {BASE_URL}{step['endpoint']}")
            if step['payload'] is not None:
                print(f"Payload:\n{json.dumps(step['payload'], indent=2)}")
            
            user_input = input("\nPress Enter to send (or 'q' to quit): ").strip().lower()
            if user_input == 'q':
                print("Exiting test sequence.")
                break
                
            try:
                if step['method'] == 'POST':
                    if step['payload'] is not None:
                        resp = await client.post(f"{BASE_URL}{step['endpoint']}", json=step['payload'])
                    else:
                        resp = await client.post(f"{BASE_URL}{step['endpoint']}")
                    
                    print(f"Response [{resp.status_code}]:")
                    try:
                        print(json.dumps(resp.json(), indent=2))
                    except json.JSONDecodeError:
                        print(resp.text)
                else:
                    print(f"Unsupported method: {step['method']}")
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
            print()
    print("Simulation done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest sequence aborted.")