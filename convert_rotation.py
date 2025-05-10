import json
import os

from xivcore.common import ActionID


def convert_to_rotation_json(file_path):
    file_name = os.path.splitext(os.path.basename(file_path))[0]

    output_file = f"output/{file_name}.json"

    actions = []

    with open(file_path, 'r') as file:
        file_content = file.read()

        """Convert the action sequence to a format compatible with Rotation class"""
        lines = file_content.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            parts = line.strip().split('|')

            if len(parts) == 2:
                action_id = ActionID(int(parts[0]))
                time_value = int(parts[1]) if parts[1] else None

                # Use the actual action name if available, otherwise use ACTION_{id}
                action_name = str(action_id.name) if action_id.name else f"ACTION_{action_id}"

                action_entry = {
                    action_name: {
                        "id": action_id,
                        "time": time_value
                    }
                }

                actions.append(action_entry)
            elif len(parts) == 1 and parts[0].isdigit():
                # Single action ID without timestamp
                action_id = ActionID(int(parts[0]))

                # Use the actual action name if available, otherwise use ACTION_{id}
                action_name = str(action_id.name) if action_id.name else f"ACTION_{action_id}"

                action_entry = {
                    action_name: {
                        "id": action_id,
                        "time": None
                    }
                }

                actions.append(action_entry)

    # Create the rotation format
    rotation_data = {
        "name": "Samurai Level 90 Rotation",
        "actions": actions
    }

    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump(rotation_data, f, indent=2)
        print(f"Rotation saved to {output_file}")


if __name__ == "__main__":
    convert_to_rotation_json(file_path="D:/project/xivzero++/ffpp/timeline/dt/eval/sam_820.txt")
