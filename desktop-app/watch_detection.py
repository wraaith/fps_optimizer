import sys
import os
import time

# Ensure we can import from the app directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from sentinel.game_detection import detect_active_game
import dataclasses

def main():
    print("Watching for active game... (Ctrl+C to stop)")
    print("Launch your games, alt-tab, open overlays, etc. to test the detection pipeline.\n")
    
    last_result = None
    last_dict = None
    
    try:
        while True:
            result = detect_active_game()
            
            # We compare the dictionary representation to detect any changes (e.g., confidence going from MEDIUM to HIGH)
            current_dict = dataclasses.asdict(result) if result else None
            
            # Ignore the timestamp for comparison so we only print on actual state changes
            if current_dict:
                current_dict.pop("detected_at", None)
            
            if current_dict != last_dict:
                if result:
                    print(f"[{time.strftime('%H:%M:%S')}] DETECTED: {result.exe_name} "
                          f"| mode={result.window_mode} | confidence={result.confidence} "
                          f"| method={result.detection_method}")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] No game detected")
                
                last_result = result
                last_dict = current_dict
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped watching.")

if __name__ == "__main__":
    main()
