import torch
from torch.utils.data import Dataset
from typing import Dict, List, Tuple, Optional, Union
import logging
import numpy as np

logger = logging.getLogger(__name__)

class BiblicalDataset(Dataset):
    """Base dataset class for biblical text data."""
    
    def __init__(
        self,
        input_ids: torch.Tensor,
        labels: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        max_length: int = 512
    ):
        """
        Initialize dataset with input tensors.
        
        Args:
            input_ids: Input tensor of shape [num_samples, seq_len]
            labels: Target tensor of shape [num_samples, seq_len] 
            attention_mask: Optional attention mask tensor
            max_length: Maximum sequence length
        """
        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids)
            
        # Validate shapes
        assert input_ids.size() == labels.size(), "Input and label tensors must have same size"
        assert input_ids.size() == attention_mask.size(), "Input and attention mask tensors must have same size"
        
        self.input_ids = input_ids
        self.labels = labels
        self.attention_mask = attention_mask
        self.max_length = max_length
        
    def __len__(self) -> int:
        return len(self.input_ids)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return (
            self.input_ids[idx][:self.max_length],
            self.labels[idx][:self.max_length],
            self.attention_mask[idx][:self.max_length]
        )

class BibleVerseDataset(BiblicalDataset):
    """Dataset specifically for Bible verses with reference tracking."""
    
    def __init__(
        self,
        verses: Dict[str, Dict[int, Dict[int, str]]],
        tokenizer,
        max_length: int = 512
    ):
        """
        Initialize Bible verse dataset.
        
        Args:
            verses: Nested dict of {book: {chapter: {verse: text}}}
            tokenizer: Tokenizer instance for encoding texts
            max_length: Maximum sequence length
        """
        self.verses = verses
        self.tokenizer = tokenizer
        self.max_length = max_length
        
        # Create verse index mapping
        self.verse_indices = []
        for book in verses:
            for chapter in verses[book]:
                for verse in verses[book][chapter]:
                    self.verse_indices.append((book, chapter, verse))
    
    def __len__(self) -> int:
        return len(self.verse_indices)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        book, chapter, verse = self.verse_indices[idx]
        text = self.verses[book][chapter][verse]
        
        # Add reference prefix to text
        reference = f"{book} {chapter}:{verse}"
        full_text = f"{reference} {text}"
        
        # Tokenize
        encoding = self.tokenizer(
            full_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "reference": reference
        }

class CommentaryDataset(BiblicalDataset):
    """Dataset for biblical commentaries with verse alignment."""
    
    def __init__(
        self,
        commentaries: List[Dict[str, Union[str, Dict]]],
        tokenizer,
        max_length: int = 512
    ):
        """
        Initialize commentary dataset.
        
        Args:
            commentaries: List of commentary entries with metadata
            tokenizer: Tokenizer instance for encoding texts
            max_length: Maximum sequence length
        """
        self.commentaries = commentaries
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self) -> int:
        return len(self.commentaries)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        entry = self.commentaries[idx]
        
        # Format reference if available
        reference = ""
        if all(k in entry for k in ["book", "chapter", "verse_start"]):
            reference = f"{entry['book']} {entry['chapter']}:{entry['verse_start']}"
            if entry.get("verse_end") and entry["verse_end"] != entry["verse_start"]:
                reference += f"-{entry['verse_end']}"
        
        # Combine reference and content
        full_text = f"{reference} {entry['content']}" if reference else entry['content']
        
        # Tokenize
        encoding = self.tokenizer(
            full_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "source": entry.get("source", "unknown"),
            "reference": reference
        }

# filepath: d:\biblical-ai\src\training\trainer.py
def train(self):
    """Training loop"""
    self.model.train()
    epoch_loss = 0
    
    for batch_idx, batch in enumerate(self.train_loader):
        # Unpack batch safely
        if not isinstance(batch, (tuple, list)) or len(batch) != 2:
            raise ValueError(f"Expected batch to be tuple of (input_ids, target_ids), got {type(batch)}")
            
        input_ids, target_ids = batch
        
        # Move to device
        input_ids = input_ids.to(self.device)
        target_ids = target_ids.to(self.device)
        
        # Rest of training loop...
        # ...existing code...