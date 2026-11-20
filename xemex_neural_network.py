
"""
XEMEX.AI Advanced Neural Network
CPU-compatible modular neural architecture.

This module provides infrastructure for structured
learning-pattern analysis. It does not diagnose disabilities.
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F

MODEL_PATH = "xemex_neural_model.pt"

# Six structured educational observation inputs.
INPUT_FEATURES = [
    "reading",
    "writing",
    "mathematics",
    "memory",
    "attention",
    "communication"
]

OUTPUT_FEATURES = [
    "reading_support",
    "writing_support",
    "math_support",
    "memory_support",
    "attention_support",
    "communication_support"
]


class XemexNeuralNetwork(nn.Module):

    def __init__(self, input_size=6, hidden_size=64, output_size=6):
        super().__init__()

        self.layer1 = nn.Linear(input_size, hidden_size)
        self.layer2 = nn.Linear(hidden_size, hidden_size)
        self.layer3 = nn.Linear(hidden_size, 32)
        self.output_layer = nn.Linear(32, output_size)

        self.dropout = nn.Dropout(0.15)

    def forward(self, x):

        x = F.relu(self.layer1(x))
        x = self.dropout(x)

        x = F.relu(self.layer2(x))
        x = self.dropout(x)

        x = F.relu(self.layer3(x))

        return torch.sigmoid(self.output_layer(x))


class XemexNeuralEngine:

    def __init__(self, model_path=MODEL_PATH):

        self.model_path = model_path
        self.device = torch.device("cpu")

        self.model = XemexNeuralNetwork().to(self.device)

        self.trained = False

        if os.path.exists(self.model_path):
            try:
                state = torch.load(
                    self.model_path,
                    map_location=self.device,
                    weights_only=True
                )

                self.model.load_state_dict(state)
                self.model.eval()
                self.trained = True

            except (RuntimeError, ValueError, OSError, EOFError):
                self.trained = False

    def get_status(self):

        return {
            "engine": "XEMEX Neural Intelligence",
            "architecture": "Multi-layer perceptron",
            "device": str(self.device),
            "trained_model_available": self.trained,
            "features": INPUT_FEATURES,
            "outputs": OUTPUT_FEATURES,
            "diagnostic_capability": False
        }

    def predict(self, observations):

        if not self.trained:
            return {
                "available": False,
                "message": (
                    "The neural network has not been trained "
                    "on validated labeled data yet."
                )
            }

        if not isinstance(observations, dict):
            raise ValueError("Observations must be a dictionary.")

        values = []

        for feature in INPUT_FEATURES:

            value = observations.get(feature)

            if isinstance(value, bool) or not isinstance(
                value, (int, float)
            ):
                raise ValueError(
                    f"Missing or invalid feature: {feature}"
                )

            if not 0 <= value <= 4:
                raise ValueError(
                    f"{feature} must be between 0 and 4."
                )

            values.append(float(value) / 4.0)

        tensor = torch.tensor(
            [values],
            dtype=torch.float32,
            device=self.device
        )

        self.model.eval()

        with torch.no_grad():
            predictions = self.model(tensor)[0].tolist()

        return {
            "available": True,
            "type": "educational_support_signals",
            "results": {
                name: round(score, 4)
                for name, score in zip(
                    OUTPUT_FEATURES, predictions
                )
            },
            "warning": (
                "Model scores are not diagnoses or "
                "validated measures of disability."
            )
        }

    def save_model(self):

        torch.save(
            self.model.state_dict(),
            self.model_path
        )

    def train_model(self, features, targets, epochs=50):

        if not features or not targets:
            raise ValueError("Training data cannot be empty.")

        if len(features) != len(targets):
            raise ValueError("Features and targets must match.")

        if epochs < 1 or epochs > 500:
            raise ValueError("Epochs must be between 1 and 500.")

        x = torch.tensor(
            features, dtype=torch.float32
        )

        y = torch.tensor(
            targets, dtype=torch.float32
        )

        if x.ndim != 2 or x.shape[1] != 6:
            raise ValueError("Training features must have 6 columns.")

        if y.ndim != 2 or y.shape[1] != 6:
            raise ValueError("Training targets must have 6 columns.")

        if not torch.isfinite(x).all() or not torch.isfinite(y).all():
            raise ValueError("Training data must be finite.")

        if (x < 0).any() or (x > 1).any():
            raise ValueError("Features must be normalized to 0-1.")

        if (y < 0).any() or (y > 1).any():
            raise ValueError("Targets must be between 0 and 1.")

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=0.001
        )

        loss_function = nn.BCELoss()

        self.model.train()

        for epoch in range(epochs):

            optimizer.zero_grad()

            predictions = self.model(x)

            loss = loss_function(predictions, y)

            loss.backward()

            optimizer.step()

        self.model.eval()
        self.save_model()
        self.trained = True

        return {
            "trained": True,
            "epochs": epochs,
            "final_training_loss": round(loss.item(), 6)
        }


# Initialize one shared neural engine.
neural_engine = XemexNeuralEngine()


def get_neural_status():
    return neural_engine.get_status()


def run_neural_analysis(observations):
    return neural_engine.predict(observations)
