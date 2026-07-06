import os
import pickle
import json
import joblib
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE

from app.core.config import settings


class ModelService:
    def __init__(self):
        self.models_dir = settings.MODELS_DIR
        self.metadata_file = os.path.join(settings.DATA_DIR, "trained_models.json")
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        
    def load_models_metadata(self) -> List[Dict]:
        """Load models metadata from file"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_models_metadata(self, models: List[Dict]):
        """Save models metadata to file"""
        with open(self.metadata_file, 'w') as f:
            json.dump(models, f, indent=2)
    
    def train_models(self, data: pd.DataFrame, data_type: str, preprocessing_options: Dict) -> Dict:
        """Train ML models based on data type and options"""
        try:
            # Prepare data
            if 'target' in data.columns:
                X = data.drop('target', axis=1)
                y = data['target']
            else:
                # If no target column, use the last column as target
                X = data.iloc[:, :-1]
                y = data.iloc[:, -1]
            
            # Handle categorical variables
            categorical_columns = X.select_dtypes(include=['object']).columns
            for col in categorical_columns:
                le = LabelEncoder()
                X[col] = le.fit_transform(X[col].astype(str))
            
            # Handle target variable
            if y.dtype == 'object':
                le_target = LabelEncoder()
                y = le_target.fit_transform(y.astype(str))
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            # Apply preprocessing
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Apply SMOTE if enabled
            if preprocessing_options.get('smote_enabled', False):
                smote = SMOTE(random_state=42)
                X_train_scaled, y_train = smote.fit_resample(X_train_scaled, y_train)
            
            # Train models based on data type
            models = {}
            model_results = []
            
            if data_type == 'enterprise':
                # Enterprise models
                models['random_forest'] = RandomForestClassifier(n_estimators=100, random_state=42)
                models['gradient_boosting'] = GradientBoostingClassifier(n_estimators=100, random_state=42)
            elif data_type == 'text':
                # Text models (simplified for demo)
                models['svm'] = SVC(kernel='rbf', random_state=42)
                models['random_forest'] = RandomForestClassifier(n_estimators=50, random_state=42)
            else:
                # General models
                try:
                    import xgboost as xgb  # Lazy import: avoids native init at API startup
                    models['xgboost'] = xgb.XGBClassifier(random_state=42)
                except Exception as xgb_error:
                    print(f"Warning: xgboost unavailable, falling back to RandomForest: {xgb_error}")
                    models['random_forest'] = RandomForestClassifier(n_estimators=100, random_state=42)
                models['svm'] = SVC(kernel='rbf', random_state=42)
            
            # Train and evaluate models
            for model_name, model in models.items():
                model.fit(X_train_scaled, y_train)
                y_pred = model.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                
                model_results.append({
                    'name': f"{data_type.title()} {model_name.replace('_', ' ').title()}",
                    'type': model_name,
                    'accuracy': accuracy,
                    'status': 'completed'
                })
            
            # Save models and preprocessing objects
            model_id = f"model_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
            model_dir = os.path.join(self.models_dir, model_id)
            os.makedirs(model_dir, exist_ok=True)
            
            # Save models
            for model_name, model in models.items():
                model_path = os.path.join(model_dir, f"{model_name}.pkl")
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
            
            # Save preprocessing objects
            scaler_path = os.path.join(model_dir, "scaler.pkl")
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            if 'le_target' in locals():
                le_path = os.path.join(model_dir, "label_encoder.pkl")
                with open(le_path, 'wb') as f:
                    pickle.dump(le_target, f)
            
            # Save model metadata
            model_metadata = {
                'id': model_id,
                'data_type': data_type,
                'created_at': datetime.now().isoformat(),
                'status': 'trained',
                'models': model_results,
                'preprocessing': {
                    'scaler': True,
                    'smote_applied': preprocessing_options.get('smote_enabled', False),
                    'feature_count': X.shape[1],
                    'sample_count': len(data)
                },
                'file_paths': {
                    'model_dir': model_dir,
                    'models': {name: f"{name}.pkl" for name in models.keys()},
                    'scaler': 'scaler.pkl',
                    'label_encoder': 'label_encoder.pkl' if 'le_target' in locals() else None
                }
            }
            
            # Update metadata file
            all_models = self.load_models_metadata()
            all_models.append(model_metadata)
            self.save_models_metadata(all_models)
            
            return {
                'model_id': model_id,
                'models': model_results,
                'metadata': model_metadata
            }
            
        except Exception as e:
            print(f"Error training models: {e}")
            raise e
    
    def get_model(self, model_id: str) -> Optional[Dict]:
        """Get model metadata by ID"""
        models = self.load_models_metadata()
        for model in models:
            if model['id'] == model_id:
                return model
        return None
    
    def get_all_models(self) -> List[Dict]:
        """Get all trained models"""
        return self.load_models_metadata()
    
    def download_model(self, model_id: str, format: str = 'pickle') -> Dict:
        """Download model in specified format"""
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        model_dir = model['file_paths']['model_dir']
        
        if format == 'pickle':
            # Create a zip file with all model files
            import zipfile
            import tempfile
            
            zip_path = os.path.join(model_dir, f"{model_id}_models.pkl.zip")
            
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                # Add model files
                for model_name, filename in model['file_paths']['models'].items():
                    file_path = os.path.join(model_dir, filename)
                    if os.path.exists(file_path):
                        zipf.write(file_path, filename)
                
                # Add preprocessing files
                scaler_path = os.path.join(model_dir, 'scaler.pkl')
                if os.path.exists(scaler_path):
                    zipf.write(scaler_path, 'scaler.pkl')
                
                le_path = os.path.join(model_dir, 'label_encoder.pkl')
                if os.path.exists(le_path):
                    zipf.write(le_path, 'label_encoder.pkl')
                
                # Add metadata
                metadata_path = os.path.join(model_dir, 'metadata.json')
                with open(metadata_path, 'w') as f:
                    json.dump(model, f, indent=2)
                zipf.write(metadata_path, 'metadata.json')
            
            return {
                'file_path': zip_path,
                'filename': f"{model_id}_models.pkl.zip",
                'format': 'pickle_zip'
            }
        
        elif format == 'onnx':
            # Convert to ONNX format (enterprise standard)
            try:
                import onnx
                from skl2onnx import convert_sklearn
                from skl2onnx.common.data_types import FloatTensorType
                
                # Get the best model
                best_model_name = max(model['models'], key=lambda x: x['accuracy'])['type']
                model_path = os.path.join(model_dir, f"{best_model_name}.pkl")
                
                with open(model_path, 'rb') as f:
                    sklearn_model = pickle.load(f)
                
                # Convert to ONNX
                initial_type = [('float_input', FloatTensorType([None, model['preprocessing']['feature_count']]))]
                onnx_model = convert_sklearn(sklearn_model, initial_types=initial_type)
                
                onnx_path = os.path.join(model_dir, f"{model_id}.onnx")
                with open(onnx_path, 'wb') as f:
                    f.write(onnx_model.SerializeToString())
                
                return {
                    'file_path': onnx_path,
                    'filename': f"{model_id}.onnx",
                    'format': 'onnx'
                }
            except ImportError:
                raise ValueError("ONNX conversion requires skl2onnx package")
        
        elif format == 'joblib':
            # Use joblib format (scikit-learn standard)
            best_model_name = max(model['models'], key=lambda x: x['accuracy'])['type']
            model_path = os.path.join(model_dir, f"{best_model_name}.pkl")
            
            # Convert to joblib
            with open(model_path, 'rb') as f:
                sklearn_model = pickle.load(f)
            
            joblib_path = os.path.join(model_dir, f"{model_id}.joblib")
            joblib.dump(sklearn_model, joblib_path)
            
            return {
                'file_path': joblib_path,
                'filename': f"{model_id}.joblib",
                'format': 'joblib'
            }
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def predict(self, model_id: str, data: List[Dict]) -> Dict:
        """Make predictions using a trained model"""
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        model_dir = model['file_paths']['model_dir']
        
        # Load preprocessing objects
        scaler_path = os.path.join(model_dir, 'scaler.pkl')
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        
        le_path = os.path.join(model_dir, 'label_encoder.pkl')
        label_encoder = None
        if os.path.exists(le_path):
            with open(le_path, 'rb') as f:
                label_encoder = pickle.load(f)
        
        # Convert data to DataFrame
        df = pd.DataFrame(data)
        
        # Handle categorical variables
        categorical_columns = df.select_dtypes(include=['object']).columns
        for col in categorical_columns:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
        
        # Scale data
        X_scaled = scaler.transform(df)
        
        # Get best model
        best_model_name = max(model['models'], key=lambda x: x['accuracy'])['type']
        model_path = os.path.join(model_dir, f"{best_model_name}.pkl")
        
        with open(model_path, 'rb') as f:
            sklearn_model = pickle.load(f)
        
        # Make predictions
        predictions = sklearn_model.predict(X_scaled)
        probabilities = sklearn_model.predict_proba(X_scaled) if hasattr(sklearn_model, 'predict_proba') else None
        
        # Convert predictions back to original labels if needed
        if label_encoder:
            predictions = label_encoder.inverse_transform(predictions)
        
        return {
            'predictions': predictions.tolist(),
            'probabilities': probabilities.tolist() if probabilities is not None else None,
            'model_used': best_model_name,
            'confidence': float(np.max(probabilities)) if probabilities is not None else None
        }

# Global instance
model_service = ModelService()
