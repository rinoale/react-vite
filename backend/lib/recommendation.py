from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Dummy Database of Items
# In a real app, this would come from your SQLite DB
ITEMS_DB = [
    {"id": 1, "name": "Refined Majestic Armor", "category": "Armor", "description": "High defense light armor with magic resistance. Refined for extra durability."},
    {"id": 2, "name": "Dragon Blade", "category": "Weapon", "description": "A sword forged from dragon scales. Deals high fire damage."},
    {"id": 3, "name": "Fire Wand", "category": "Weapon", "description": "A wand infused with fire magic. Increases fire spell damage."},
    {"id": 4, "name": "Majestic Gauntlets", "category": "Armor", "description": "Gauntlets that pair well with Majestic Armor. Increases defense."},
    {"id": 5, "name": "Ice Shield", "category": "Armor", "description": "Shield that freezes enemies on contact. High defense against ice."},
    {"id": 6, "name": "Phoenix Feather", "category": "Consumable", "description": "Revives a fallen ally with full health. Rare item."},
    {"id": 7, "name": "Rusty Sword", "category": "Weapon", "description": "An old sword. Low damage, low durability."},
    {"id": 8, "name": "Dragon Scale Helm", "category": "Armor", "description": "Helmet made of dragon scales. Fire resistance."},
]

class Recommender:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.update_matrix()

    def update_matrix(self):
        """Update the TF-IDF matrix based on current ITEMS_DB"""
        # Combine name and description for content-based filtering
        self.corpus = [f"{item['name']} {item['category']} {item['description']}" for item in ITEMS_DB]
        self.tfidf_matrix = self.vectorizer.fit_transform(self.corpus)

    def get_recommendations(self, item_id: int, top_k: int = 3):
        """
        Content-Based Filtering:
        Find items similar to the given item_id based on text description.
        """
        # Find index of the item
        try:
            item_idx = next(i for i, item in enumerate(ITEMS_DB) if item["id"] == item_id)
        except StopIteration:
            return []

        # Calculate cosine similarity between this item and all others
        cosine_sim = cosine_similarity(self.tfidf_matrix[item_idx:item_idx+1], self.tfidf_matrix).flatten()
        
        # Get top_k indices (excluding itself)
        # argsort sorts ascending, so we take the end
        related_indices = cosine_sim.argsort()[:-top_k-2:-1] 
        
        recommendations = []
        for idx in related_indices:
            if idx != item_idx: # Skip the item itself
                recommendations.append({
                    "item": ITEMS_DB[idx],
                    "score": float(cosine_sim[idx])
                })
        
        return recommendations[:top_k]

    def recommend_for_user(self, user_history_ids: list[int], top_k: int = 3):
        """
        Hybrid/User-Basedish:
        Aggregate recommendations based on all items in user's history.
        """
        if not user_history_ids:
            return ITEMS_DB[:top_k] # Default to first few items if no history

        # Get recommendations for each item in history
        candidates = {}
        for hist_id in user_history_ids:
            recs = self.get_recommendations(hist_id, top_k=top_k)
            for rec in recs:
                item_id = rec['item']['id']
                if item_id in user_history_ids: continue # Skip items already seen
                
                if item_id not in candidates:
                    candidates[item_id] = {"item": rec['item'], "score": 0}
                candidates[item_id]["score"] += rec["score"] # Sum scores if recommended multiple times

        # Sort by accumulated score
        sorted_candidates = sorted(candidates.values(), key=lambda x: x['score'], reverse=True)
        return [c['item'] for c in sorted_candidates[:top_k]]

# Singleton instance
recommender = Recommender()
