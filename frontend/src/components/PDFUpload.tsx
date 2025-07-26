import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  DocumentTextIcon,
  CloudArrowUpIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

interface PDFUploadProps {
  onUploadComplete: (files: File[]) => void;
  onCancel: () => void;
}

interface UploadFile {
  file: File;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  progress: number;
  error?: string;
}

const PDFUpload: React.FC<PDFUploadProps> = ({ onUploadComplete, onCancel }) => {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadFile[] = acceptedFiles.map(file => ({
      file,
      status: 'pending',
      progress: 0
    }));
    setUploadFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  });

  const removeFile = (index: number) => {
    setUploadFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUploadFiles = async () => {
    if (uploadFiles.length === 0) return;

    setIsUploading(true);
    const formData = new FormData();
    
    uploadFiles.forEach((uploadFile, index) => {
      formData.append('files', uploadFile.file);
    });

    try {
      // Update status to uploading
      setUploadFiles(prev => prev.map(file => ({ ...file, status: 'uploading' as const })));

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadFiles(prev => prev.map(file => ({
          ...file,
          progress: Math.min(file.progress + Math.random() * 20, 90)
        })));
      }, 200);

      // Make API call to backend
      console.log('Uploading files:', uploadFiles.map(f => f.file.name));
      const response = await fetch('http://localhost:8000/api/v1/upload/', {
        method: 'POST',
        body: formData,
      });

      console.log('Upload response status:', response.status);

      clearInterval(progressInterval);

      if (response.ok) {
        const result = await response.json();
        console.log('Upload response:', result);
        
        // Check if any files failed
        const hasErrors = result.data?.results?.some((r: any) => r.status === 'error');
        
        if (hasErrors) {
          // Update files based on individual results
          setUploadFiles(prev => prev.map((file, index) => {
            const fileResult = result.data.results[index];
            return {
              ...file,
              status: fileResult?.status === 'success' ? 'completed' as const : 'error' as const,
              progress: fileResult?.status === 'success' ? 100 : 0,
              error: fileResult?.message || 'Upload failed'
            };
          }));
        } else {
          // Update all files to completed
          setUploadFiles(prev => prev.map(file => ({
            ...file,
            status: 'completed' as const,
            progress: 100
          })));

          // Call the completion callback
          onUploadComplete(uploadFiles.map(uf => uf.file));
        }
      } else {
        const errorData = await response.json();
        console.error('Upload failed with status:', response.status, 'Error:', errorData);
        throw new Error(errorData.detail || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      
      // Update all files to error with specific error message
      setUploadFiles(prev => prev.map(file => ({
        ...file,
        status: 'error' as const,
        error: error instanceof Error ? error.message : 'Upload failed. Please try again.'
      })));
    } finally {
      setIsUploading(false);
    }
  };

  const getStatusIcon = (status: UploadFile['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'error':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <DocumentTextIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: UploadFile['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'error':
        return 'bg-red-100 text-red-800';
      case 'uploading':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">Upload PDF Documents</h3>
        <p className="text-gray-600">
          Upload your PDF files to create knowledge embeddings
        </p>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
          isDragActive
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input {...getInputProps()} />
        <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        {isDragActive ? (
          <p className="text-lg font-medium text-indigo-600">Drop the PDF files here...</p>
        ) : (
          <div>
            <p className="text-lg font-medium text-gray-900 mb-2">
              Drag & drop PDF files here
            </p>
            <p className="text-gray-500">or click to browse files</p>
          </div>
        )}
      </div>

      {/* File List */}
      {uploadFiles.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-semibold text-gray-900">Selected Files</h4>
          <div className="space-y-3">
            {uploadFiles.map((uploadFile, index) => (
              <div
                key={index}
                className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between"
              >
                <div className="flex items-center space-x-3 flex-1">
                  {getStatusIcon(uploadFile.status)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {uploadFile.file.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(uploadFile.file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  {/* Progress Bar */}
                  {uploadFile.status === 'uploading' && (
                    <div className="w-24 bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${uploadFile.progress}%` }}
                      />
                    </div>
                  )}

                  {/* Status Badge */}
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(uploadFile.status)}`}>
                    {uploadFile.status}
                  </span>

                  {/* Remove Button */}
                  <button
                    onClick={() => removeFile(index)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Messages */}
      {uploadFiles.some(f => f.status === 'error') && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mt-0.5" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Upload Errors</h3>
              <div className="mt-2 text-sm text-red-700">
                {uploadFiles
                  .filter(f => f.status === 'error')
                  .map((f, i) => (
                    <p key={i}>• {f.file.name}: {f.error}</p>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-end space-x-4">
        <button
          onClick={onCancel}
          className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleUploadFiles}
          disabled={uploadFiles.length === 0 || isUploading}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            uploadFiles.length === 0 || isUploading
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-indigo-600 text-white hover:bg-indigo-700'
          }`}
        >
          {isUploading ? 'Uploading...' : 'Upload Files'}
        </button>
      </div>
    </div>
  );
};

export default PDFUpload; 