# src/training/trainer.py
import torch
from torch.utils.data import DataLoader
import json
import os
import sys
from transformers import get_linear_schedule_with_warmup

# Use relative imports
from ..model.architecture import BiblicalTransformer, BiblicalTransformerConfig
from ..data.preprocessing import load_processed_data
from ..training.loss import TheologicalLoss
from ..training.optimization import get_optimizer_and_scheduler
from ..utils.logger import setup_logger

# Get the project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Add the project root to Python path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Check for __init__.py files
init_files_present = True
for subdir in ['src', 'src/model', 'src/data', 'src/training', 'src/utils']:
    init_file = os.path.join(PROJECT_ROOT, subdir, '__init__.py')
    if not os.path.exists(init_file):
        print(f"Error: Missing __init__.py in {subdir}")
        init_files_present = False
        break

if not init_files_present:
    print("Error: Missing __init__.py files. Please create them.")
    sys.exit(1)

class Trainer:
    def __init__(self, config_path: str):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Create model config from model_params
        self.model_config = BiblicalTransformerConfig(**self.config['model_params'])
        
        # Setup device and logger
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        os.makedirs(self.config['output_params']['log_dir'], exist_ok=True)  # Fixed typo here
        self.logger = setup_logger("trainer", 
                                 os.path.join(self.config['output_params']['log_dir'], 
                                            "training.log"))
        
        # Initialize components
        self.setup_model()
        self.setup_data()
        self.setup_training_components()

    def setup_model(self):
        """Initialize model with error handling."""
        try:
            self.model = BiblicalTransformer(self.model_config).to(self.device)
            self.logger.info("Model initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize model: {str(e)}")
            raise

    def setup_data(self):
        """Initialize data loaders with proper path handling."""
        data_config = self.config['data_params']
        try:
            self.train_data, self.val_data = load_processed_data(
                os.path.join(PROJECT_ROOT, data_config['data_path'])
            )
            self.train_loader = DataLoader(
                self.train_data, 
                batch_size=self.config['training_params']['batch_size'],
                shuffle=True
            )
            self.val_loader = DataLoader(
                self.val_data,
                batch_size=self.config['training_params']['batch_size'],
                shuffle=False
            )
            self.logger.info(f"Loaded {len(self.train_data)} training samples and {len(self.val_data)} validation samples")
        except Exception as e:
            self.logger.error(f"Failed to load data: {str(e)}")
            raise

    def setup_training_components(self):
        """Initialize loss, optimizer and scheduler with config params."""
        training_params = self.config['training_params']
        try:
            self.criterion = TheologicalLoss()
            self.optimizer, self.scheduler = get_optimizer_and_scheduler(
                self.model.parameters(),
                lr=training_params['learning_rate'],
                warmup_steps=training_params['warmup_steps'],
                total_steps=len(self.train_loader) * training_params['epochs']
            )
            self.logger.info("Training components initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize training components: {str(e)}")
            raise

    def setup_training(self):
        self.scheduler = get_linear_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=self.config.warmup_steps,
            num_training_steps=len(self.train_loader) * self.config.epochs
        )

    def train(self):
        """Training loop with proper loss handling"""
        self.model.train()
        epoch_loss = 0
        best_val_loss = float('inf')
        
        for batch_idx, batch in enumerate(self.train_loader):
            # Unpack batch
            input_ids, labels, attention_mask = batch
            
            # Move to device
            input_ids = input_ids.to(self.device)
            labels = labels.to(self.device)
            attention_mask = attention_mask.to(self.device)
            
            # Zero gradients
            self.optimizer.zero_grad()
            
            # Forward pass
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )
            
            # Calculate loss
            loss = self.criterion(outputs['logits'], labels)
            
            # Backward pass
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            self.scheduler.step()
            
            # Track loss
            epoch_loss += loss.item()
            if batch_idx % 100 == 0:
                self.logger.info(f"Batch {batch_idx}, Loss: {loss.item():.4f}")
        
        avg_train_loss = epoch_loss / len(self.train_loader)
        
        # Validation phase
        val_loss = self.validate()
        
        self.logger.info(f"Train Loss = {avg_train_loss:.4f}, Val Loss = {val_loss:.4f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(self.model.state_dict(), 
                      self.config['output_params']['model_save_path'])
            self.logger.info(f"Saved best model with Val Loss: {best_val_loss:.4f}")

    def validate(self):
        """Validation loop with consistent output handling"""
        self.model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for batch in self.val_loader:
                input_ids, labels, attention_mask = batch
                
                # Move to device
                input_ids = input_ids.to(self.device)
                labels = labels.to(self.device)
                attention_mask = attention_mask.to(self.device)
                
                # Forward pass
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask
                )
                
                # Calculate loss
                loss = self.criterion(outputs['logits'], labels)
                val_loss += loss.item()
                
        return val_loss / len(self.val_loader)

if __name__ == "__main__":
    trainer = Trainer("config/training_config.json")
    trainer.train()