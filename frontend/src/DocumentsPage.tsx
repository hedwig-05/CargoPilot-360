
import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Eye,
  FileCheck2,
  FileSearch,
  FileText,
  RefreshCw,
  Upload,
  X,
} from 'lucide-react'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

interface ShipmentOption {
  shipment_id: number
  shipment_ref?: string
  container_no?: string | null
}

interface ShipmentDocument {
  document_id: number
  shipment_id: number
  document_type: string
  file_name: string
  file_hash: string | null
  extracted_fields: Record<string, unknown> | null
  extraction_status: string
  validation_status: string
  version_no: number
  uploaded_by: number
  upload_date: string
}

type ValidationRecord = Record<string, unknown>

interface DocumentsPageProps {
  shipments: ShipmentOption[]
}

function getStatusClass(status: string) {
  const value = status.toUpperCase()

  if (
    value === 'EXTRACTED' ||
    value === 'MATCH' ||
    value === 'VALIDATED' ||
    value === 'COMPLETED'
  ) {
    return 'doc-status-success'
  }

  if (
    value === 'MISMATCH' ||
    value === 'FAILED' ||
    value === 'ERROR'
  ) {
    return 'doc-status-danger'
  }

  if (
    value === 'PROCESSING' ||
    value === 'PENDING' ||
    value === 'NOT_VALIDATED'
  ) {
    return 'doc-status-pending'
  }

  return 'doc-status-neutral'
}

function formatLabel(value: string) {
  return value
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatDate(value: string) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleString()
}

function getValidationValue(
  record: ValidationRecord,
  possibleKeys: string[],
) {
  for (const key of possibleKeys) {
    const value = record[key]

    if (value !== undefined && value !== null && value !== '') {
      return String(value)
    }
  }

  return '—'
}

export default function DocumentsPage({
  shipments,
}: DocumentsPageProps) {
  const [selectedShipmentId, setSelectedShipmentId] = useState<number | null>(
    shipments[0]?.shipment_id ?? null,
  )

  const [documents, setDocuments] = useState<ShipmentDocument[]>([])
  const [validations, setValidations] = useState<ValidationRecord[]>([])

  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const [error, setError] = useState('')
  const [uploadMessage, setUploadMessage] = useState('')

  const [documentType, setDocumentType] = useState('COMMERCIAL_INVOICE')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedDocument, setSelectedDocument] =
    useState<ShipmentDocument | null>(null)

  const token = sessionStorage.getItem('cargopilot-token')

  const selectedShipment = useMemo(
    () =>
      shipments.find(
        (shipment) => shipment.shipment_id === selectedShipmentId,
      ),
    [shipments, selectedShipmentId],
  )

  useEffect(() => {
    if (
      selectedShipmentId === null &&
      shipments.length > 0
    ) {
      setSelectedShipmentId(shipments[0].shipment_id)
    }
  }, [shipments, selectedShipmentId])

  async function loadDocuments() {
    if (!selectedShipmentId || !token) return

    setIsLoading(true)
    setError('')

    try {
      const headers = {
        Authorization: `Bearer ${token}`,
      }

      const [documentsResponse, validationsResponse] = await Promise.all([
        fetch(
          `${API_BASE_URL}/api/shipments/${selectedShipmentId}/documents`,
          { headers },
        ),
        fetch(
          `${API_BASE_URL}/api/shipments/${selectedShipmentId}/validations`,
          { headers },
        ),
      ])

      if (!documentsResponse.ok) {
        throw new Error('Unable to load shipment documents.')
      }

      if (!validationsResponse.ok) {
        throw new Error('Unable to load document validation records.')
      }

      const documentsData = await documentsResponse.json()
      const validationsData = await validationsResponse.json()

      if (!Array.isArray(documentsData)) {
        throw new Error('Unexpected documents response from the server.')
      }

      if (!Array.isArray(validationsData)) {
        throw new Error('Unexpected validation response from the server.')
      }

      setDocuments(documentsData)
      setValidations(validationsData)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Something went wrong while loading documents.',
      )
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    setSelectedDocument(null)
    setUploadMessage('')
    setError('')
    setDocuments([])
    setValidations([])

    if (!selectedShipmentId || !token) return

    let cancelled = false

    async function load() {
      setIsLoading(true)

      try {
        const headers = {
          Authorization: `Bearer ${token}`,
        }

        const [documentsResponse, validationsResponse] = await Promise.all([
          fetch(
            `${API_BASE_URL}/api/shipments/${selectedShipmentId}/documents`,
            { headers },
          ),
          fetch(
            `${API_BASE_URL}/api/shipments/${selectedShipmentId}/validations`,
            { headers },
          ),
        ])

        if (!documentsResponse.ok) {
          throw new Error('Unable to load shipment documents.')
        }

        if (!validationsResponse.ok) {
          throw new Error('Unable to load validation records.')
        }

        const documentsData = await documentsResponse.json()
        const validationsData = await validationsResponse.json()

        if (!Array.isArray(documentsData) || !Array.isArray(validationsData)) {
          throw new Error('The server returned an unexpected response.')
        }

        if (!cancelled) {
          setDocuments(documentsData)
          setValidations(validationsData)
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load documents.',
          )
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [selectedShipmentId, token])

  async function handleUpload() {
    if (!selectedShipmentId || !selectedFile || !token) {
      setError('Select a shipment and choose a document file first.')
      return
    }

    if (!documentType.trim()) {
      setError('Enter a document type.')
      return
    }

    setIsUploading(true)
    setError('')
    setUploadMessage('')

    try {
      const formData = new FormData()
      formData.append('document_type', documentType.trim())
      formData.append('file', selectedFile)

      const response = await fetch(
        `${API_BASE_URL}/api/shipments/${selectedShipmentId}/documents/upload`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        },
      )

      const responseText = await response.text()

      if (!response.ok) {
        let message = responseText || 'Document upload failed.'

        try {
          const parsed = JSON.parse(responseText)
          message = parsed.detail || message
        } catch {
          // The server may return a plain-text error.
        }

        throw new Error(message)
      }

      let successMessage = 'Document uploaded successfully.'

      try {
        const parsed = JSON.parse(responseText)
        if (typeof parsed === 'string' && parsed.trim()) {
          successMessage = parsed
        }
      } catch {
        if (responseText.trim()) {
          successMessage = responseText
        }
      }

      setUploadMessage(successMessage)
      setSelectedFile(null)

      const fileInput = document.getElementById(
        'document-file-input',
      ) as HTMLInputElement | null

      if (fileInput) fileInput.value = ''

      await loadDocuments()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'An error occurred during upload.',
      )
    } finally {
      setIsUploading(false)
    }
  }

  const extractedCount = documents.filter(
    (document) => document.extraction_status === 'EXTRACTED',
  ).length

  const validatedCount = documents.filter((document) => {
    const status = document.validation_status.toUpperCase()

    return status === 'VALIDATED' || status === 'COMPLETED'
  }).length

  const pendingCount = documents.filter((document) => {
    const status = document.extraction_status.toUpperCase()

    return status !== 'EXTRACTED'
  }).length

  return (
    <section className="documents-page">
      <div className="documents-heading">
        <div>
          <div className="documents-eyebrow">DOCUMENT MANAGEMENT</div>
          <h1>Documents</h1>
          <p>
            Manage shipment documents, review extracted information and
            inspect validation records.
          </p>
        </div>

        <button
          className="document-action-button"
          onClick={loadDocuments}
          disabled={isLoading || !selectedShipmentId}
        >
          <RefreshCw
            size={15}
            className={isLoading ? 'refresh-spinning' : ''}
          />
          {isLoading ? 'Refreshing' : 'Refresh'}
        </button>
      </div>

      <div className="document-shipment-selector">
        <div>
          <label htmlFor="document-shipment">
            SELECT SHIPMENT
          </label>

          <select
            id="document-shipment"
            value={selectedShipmentId ?? ''}
            onChange={(event) =>
              setSelectedShipmentId(
                event.target.value ? Number(event.target.value) : null,
              )
            }
          >
            {shipments.map((shipment) => (
              <option
                key={shipment.shipment_id}
                value={shipment.shipment_id}
              >
                {shipment.shipment_ref || `Shipment ${shipment.shipment_id}`}
                {shipment.container_no
                  ? ` — ${shipment.container_no}`
                  : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="document-selected-reference">
          <span>ACTIVE SHIPMENT</span>
          <strong>
            {selectedShipment?.shipment_ref ||
              (selectedShipment
                ? `Shipment ${selectedShipment.shipment_id}`
                : 'No shipment selected')}
          </strong>
        </div>
      </div>

      {error && (
        <div className="document-alert document-alert-error">
          <AlertCircle size={17} />
          <span>{error}</span>
          <button
            aria-label="Dismiss error"
            onClick={() => setError('')}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {uploadMessage && (
        <div className="document-alert document-alert-success">
          <CheckCircle2 size={17} />
          <span>{uploadMessage}</span>
          <button
            aria-label="Dismiss message"
            onClick={() => setUploadMessage('')}
          >
            <X size={16} />
          </button>
        </div>
      )}

      <div className="document-stat-grid">
        <div className="document-stat-card">
          <div className="document-stat-icon">
            <FileText size={19} />
          </div>
          <div>
            <span>TOTAL DOCUMENTS</span>
            <strong>{documents.length}</strong>
          </div>
        </div>

        <div className="document-stat-card">
          <div className="document-stat-icon">
            <FileCheck2 size={19} />
          </div>
          <div>
            <span>EXTRACTED</span>
            <strong>{extractedCount}</strong>
          </div>
        </div>

        <div className="document-stat-card">
          <div className="document-stat-icon">
            <Clock3 size={19} />
          </div>
          <div>
            <span>AWAITING EXTRACTION</span>
            <strong>{pendingCount}</strong>
          </div>
        </div>

        <div className="document-stat-card">
          <div className="document-stat-icon">
            <CheckCircle2 size={19} />
          </div>
          <div>
            <span>VALIDATED</span>
            <strong>{validatedCount}</strong>
          </div>
        </div>
      </div>

      <div className="documents-main-grid">
        <div className="document-panel document-repository">
          <div className="document-panel-heading">
            <div>
              <h2>Document Repository</h2>
              <p>Documents associated with the selected shipment</p>
            </div>

            <span className="document-count">
              {documents.length} FILE{documents.length === 1 ? '' : 'S'}
            </span>
          </div>

          {isLoading ? (
            <div className="document-empty-state">
              <RefreshCw size={24} className="refresh-spinning" />
              <strong>Loading documents</strong>
              <span>Retrieving shipment records...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="document-empty-state">
              <FileSearch size={30} />
              <strong>No documents found</strong>
              <span>
                Upload a document to begin managing this shipment's records.
              </span>
            </div>
          ) : (
            <div className="document-table-wrap">
              <table className="document-table">
                <thead>
                  <tr>
                    <th>DOCUMENT</th>
                    <th>EXTRACTION</th>
                    <th>VALIDATION</th>
                    <th>VERSION</th>
                    <th></th>
                  </tr>
                </thead>

                <tbody>
                  {documents.map((document) => (
                    <tr key={document.document_id}>
                      <td>
                        <div className="document-file-cell">
                          <div className="document-file-icon">
                            <FileText size={17} />
                          </div>
                          <div>
                            <strong>{document.file_name}</strong>
                            <span>{formatLabel(document.document_type)}</span>
                          </div>
                        </div>
                      </td>

                      <td>
                        <span
                          className={`document-status ${getStatusClass(
                            document.extraction_status,
                          )}`}
                        >
                          {formatLabel(document.extraction_status)}
                        </span>
                      </td>

                      <td>
                        <span
                          className={`document-status ${getStatusClass(
                            document.validation_status,
                          )}`}
                        >
                          {formatLabel(document.validation_status)}
                        </span>
                      </td>

                      <td>v{document.version_no}</td>

                      <td>
                        <button
                          className="document-view-button"
                          onClick={() => setSelectedDocument(document)}
                          title="View extracted fields"
                        >
                          <Eye size={15} />
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="document-panel document-upload-panel">
          <div className="document-panel-heading">
            <div>
              <h2>Upload Document</h2>
              <p>Add a document to the selected shipment</p>
            </div>
            <Upload size={19} />
          </div>

          <div className="document-upload-form">
            <div className="document-form-field">
              <label htmlFor="document-type">DOCUMENT TYPE</label>
              <input
                id="document-type"
                type="text"
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value)}
                placeholder="e.g. COMMERCIAL_INVOICE"
              />
              <span>
                Enter the document type supported by the backend.
              </span>
            </div>

            <div className="document-form-field">
              <label htmlFor="document-file-input">SELECT FILE</label>
              <input
                id="document-file-input"
                type="file"
                onChange={(event) =>
                  setSelectedFile(event.target.files?.[0] || null)
                }
              />

              {selectedFile && (
                <div className="document-selected-file">
                  <FileText size={15} />
                  <span>{selectedFile.name}</span>
                  <button
                    onClick={() => {
                      setSelectedFile(null)
                      const input = document.getElementById(
                        'document-file-input',
                      ) as HTMLInputElement | null
                      if (input) input.value = ''
                    }}
                    aria-label="Remove selected file"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}
            </div>

            <button
              className="document-action-button document-upload-button"
              onClick={handleUpload}
              disabled={
                isUploading ||
                !selectedFile ||
                !selectedShipmentId ||
                !documentType.trim()
              }
            >
              <Upload size={16} />
              {isUploading ? 'Uploading...' : 'Upload Document'}
            </button>

            <p className="document-upload-note">
              The document will be uploaded against the selected shipment.
              Extraction and validation statuses will be refreshed after upload.
            </p>
          </div>
        </div>
      </div>

      <div className="document-panel document-validation-panel">
        <div className="document-panel-heading">
          <div>
            <h2>Validation Records</h2>
            <p>Validation results returned by the shipment API</p>
          </div>
          <FileCheck2 size={19} />
        </div>

        {validations.length === 0 ? (
          <div className="document-validation-empty">
            <CheckCircle2 size={19} />
            <span>
              No validation records are currently available for this shipment.
            </span>
          </div>
        ) : (
          <div className="document-table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>DOCUMENT</th>
                  <th>FIELD</th>
                  <th>DOCUMENT VALUE</th>
                  <th>SHIPMENT VALUE</th>
                  <th>RESULT</th>
                </tr>
              </thead>

              <tbody>
                {validations.map((record, index) => {
                  const result = getValidationValue(record, [
                    'result',
                    'validation_status',
                    'status',
                  ])

                  return (
                    <tr key={String(record.validation_id ?? index)}>
                      <td>
                        {getValidationValue(record, [
                          'document_type',
                          'document_id',
                        ])}
                      </td>
                      <td>
                        {getValidationValue(record, [
                          'field_name',
                          'field',
                          'field_key',
                        ])}
                      </td>
                      <td>
                        {getValidationValue(record, [
                          'document_value',
                          'source_value',
                          'extracted_value',
                        ])}
                      </td>
                      <td>
                        {getValidationValue(record, [
                          'shipment_value',
                          'target_value',
                          'expected_value',
                        ])}
                      </td>
                      <td>
                        <span
                          className={`document-status ${getStatusClass(result)}`}
                        >
                          {formatLabel(result)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedDocument && (
        <div
          className="document-modal-backdrop"
          onClick={() => setSelectedDocument(null)}
        >
          <div
            className="document-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="document-modal-heading">
              <div>
                <span>DOCUMENT DETAILS</span>
                <h2>{selectedDocument.file_name}</h2>
                <p>{formatLabel(selectedDocument.document_type)}</p>
              </div>

              <button
                onClick={() => setSelectedDocument(null)}
                aria-label="Close document details"
              >
                <X size={20} />
              </button>
            </div>

            <div className="document-modal-metadata">
              <div>
                <span>DOCUMENT ID</span>
                <strong>{selectedDocument.document_id}</strong>
              </div>
              <div>
                <span>VERSION</span>
                <strong>{selectedDocument.version_no}</strong>
              </div>
              <div>
                <span>EXTRACTION</span>
                <strong>{formatLabel(selectedDocument.extraction_status)}</strong>
              </div>
              <div>
                <span>VALIDATION</span>
                <strong>{formatLabel(selectedDocument.validation_status)}</strong>
              </div>
              <div>
                <span>UPLOAD DATE</span>
                <strong>{formatDate(selectedDocument.upload_date)}</strong>
              </div>
            </div>

            <div className="document-extracted-fields-heading">
              <h3>Extracted Fields</h3>
              <span>
                {Object.keys(selectedDocument.extracted_fields || {}).length}{' '}
                FIELDS
              </span>
            </div>

            {selectedDocument.extracted_fields &&
            Object.keys(selectedDocument.extracted_fields).length > 0 ? (
              <div className="document-fields-grid">
                {Object.entries(selectedDocument.extracted_fields).map(
                  ([key, value]) => (
                    <div className="document-field-item" key={key}>
                      <span>{formatLabel(key)}</span>
                      <strong>
                        {value === null || value === undefined
                          ? '—'
                          : typeof value === 'object'
                            ? JSON.stringify(value)
                            : String(value)}
                      </strong>
                    </div>
                  ),
                )}
              </div>
            ) : (
              <div className="document-validation-empty">
                No extracted fields are available for this document.
              </div>
            )}

            <div className="document-modal-footer">
              <button
                className="document-action-button"
                onClick={() => setSelectedDocument(null)}
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
