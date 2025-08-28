import os
from dotenv import load_dotenv
import fal_client

# Define the path to the .env file relative to the script's location
# This assumes your .env file is in the parent directory of your script
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

# Verify that the FAL_KEY variable is loaded
fal_key = os.getenv("FAL_KEY")
if fal_key is None:
    raise ValueError("FAL_KEY environment variable is not set. Please check your .env file.")

def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(log["message"])

print("Starting Fal AI subscription for text-to-video...")
result = fal_client.subscribe(
    "fal-ai/minimax/hailuo-02/standard/text-to-video",
    arguments={
        "prompt": "A Galactic Smuggler is a rogue figure with a cybernetic arm and a well-worn coat that hints at many dangerous escapades across the galaxy. Their ship is filled with rare and exotic treasures from distant planets, concealed in hidden compartments, showing their expertise in illicit trade. Their belt is adorned with energy-based weapons, ready to be drawn at any moment to protect themselves or escape from tight situations. This character thrives in the shadows of space, navigating between the law and chaos with stealth and wit, always seeking the next big score while evading bounty hunters and law enforcement. The rogue's ship, rugged yet efficient, serves as both a home and a tool for their dangerous lifestyle. The treasures they collect reflect the diverse and intriguing worlds they've encountered—alien artifacts, rare minerals, and artifacts of unknown origin. Their reputation precedes them, with whispers of their dealings and the deadly encounters that often follow. A master of negotiation and deception, the Galactic Smuggler navigates the cosmos with an eye on the horizon, always one step ahead of those who pursue them."
    },
    with_logs=True,
    on_queue_update=on_queue_update,
)

print("\n--- Result ---")
print(result)