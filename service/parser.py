import yaml
from typing import Any, Dict, List

class BotTemplateParser:
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.data = self._load_yaml()
        self._validate()

    def _load_yaml(self) -> Dict[str, Any]:
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            print(f"DEBUG: Загруженные данные из {self.yaml_path}: {data}")
            return data

    def _validate(self):
        print(f"DEBUG: Валидация данных: {self.data}")
        if 'steps' not in self.data or not isinstance(self.data['steps'], list):
            print(f"DEBUG: 'steps' не найден или не является списком. Тип: {type(self.data.get('steps'))}")
            raise ValueError('YAML must contain a list of steps')
        for step in self.data['steps']:
            if 'name' not in step or 'message' not in step:
                raise ValueError(f"Each step must have 'name' and 'message': {step}")

    def get_steps(self) -> List[Dict[str, Any]]:
        return self.data['steps']

    def get_step_by_name(self, name: str) -> Dict[str, Any]:
        for step in self.data['steps']:
            if step['name'] == name:
                return step
        raise KeyError(f"Step with name '{name}' not found")

    def get_name(self) -> str:
        return self.data.get('name', "unknown")
