import Foundation

enum SpotRuntimeState: Equatable {
    case offline
    case starting
    case online
    case error(String)

    var label: String {
        switch self {
        case .offline:
            "Offline"
        case .starting:
            "Starting"
        case .online:
            "Online"
        case .error:
            "Error"
        }
    }
}

enum SpotAppPage: String, CaseIterable, Identifiable {
    case dashboard
    case control
    case intake
    case review
    case operations

    var id: String { rawValue }

    var title: String {
        switch self {
        case .dashboard: "Dashboard"
        case .control: "Control"
        case .intake: "Intake"
        case .review: "Review"
        case .operations: "Operations"
        }
    }
}

enum SpotMetricHistoryKind {
    case processedRows
    case totalRows
    case progressPercent
    case avgSecondsPerRow
    case elapsedSeconds
    case reviewRequiredRows
    case pendingReviewRows
    case segmentQueue
    case runRecords
    case acceptedUploads
    case rowsRemaining
    case threatRate
    case projectedThreats
    case judgedRows
}

struct SpotAuthSession: Decodable {
    let sessionID: String
    let role: String
    let actorName: String
    let authEnabled: Bool?

    private enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case role
        case actorName = "actor_name"
        case authEnabled = "auth_enabled"
    }
}

struct SpotAuthSessionResponse: Decodable {
    let authEnabled: Bool
    let authenticated: Bool
    let session: SpotAuthSession?

    private enum CodingKeys: String, CodingKey {
        case authEnabled = "auth_enabled"
        case authenticated
        case session
    }
}

struct SpotHealthConfig: Decodable {
    let ok: Bool
    let status: String
    let launch: SpotHealthLaunch
    let authEnabled: Bool
    let version: String

    private enum CodingKeys: String, CodingKey {
        case ok
        case status
        case launch
        case authEnabled = "auth_enabled"
        case version
    }
}

struct SpotHealthLaunch: Decodable {
    let ready: Bool
}

struct SpotRunReviewSummary: Decodable {
    let reviewRequiredRows: Int
    let reviewedRows: Int
    let pendingRows: Int

    private enum CodingKeys: String, CodingKey {
        case reviewRequiredRows = "review_required_rows"
        case reviewedRows = "reviewed_rows"
        case pendingRows = "pending_rows"
    }
}

struct SpotRunProgress: Decodable {
    let state: String?
    let message: String?
    let totalRows: Int?
    let processedRows: Int?
    let progressPercentage: Double?
    let startedAt: String?
    let completedAt: String?

    private enum CodingKeys: String, CodingKey {
        case state
        case message
        case totalRows = "total_rows"
        case processedRows = "processed_rows"
        case progressPercentage = "progress_percentage"
        case startedAt = "started_at"
        case completedAt = "completed_at"
    }

    init(
        state: String?,
        message: String?,
        totalRows: Int?,
        processedRows: Int?,
        progressPercentage: Double?,
        startedAt: String?,
        completedAt: String?
    ) {
        self.state = state
        self.message = message
        self.totalRows = totalRows
        self.processedRows = processedRows
        self.progressPercentage = progressPercentage
        self.startedAt = startedAt
        self.completedAt = completedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        state = try container.decodeIfPresent(String.self, forKey: .state)
        message = try container.decodeIfPresent(String.self, forKey: .message)
        totalRows = try container.decodeIfPresent(Int.self, forKey: .totalRows)
        processedRows = try container.decodeIfPresent(Int.self, forKey: .processedRows)
        progressPercentage = try container.decodeIfPresent(Double.self, forKey: .progressPercentage)
        startedAt = Self.decodeFlexibleTimestamp(from: container, forKey: .startedAt)
        completedAt = Self.decodeFlexibleTimestamp(from: container, forKey: .completedAt)
    }

    private static func decodeFlexibleTimestamp(
        from container: KeyedDecodingContainer<CodingKeys>,
        forKey key: CodingKeys
    ) -> String? {
        if let stringValue = try? container.decodeIfPresent(String.self, forKey: key) {
            return stringValue
        }
        if let intValue = try? container.decodeIfPresent(Int.self, forKey: key) {
            return String(intValue)
        }
        if let doubleValue = try? container.decodeIfPresent(Double.self, forKey: key) {
            return String(doubleValue)
        }
        return nil
    }
}

struct SpotClassifyStatus: Decodable {
    let runID: String
    let effectiveState: String
    let running: Bool
    let paused: Bool
    let pid: Int?
    let progress: SpotRunProgress?

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case effectiveState = "effective_state"
        case running
        case paused
        case pid
        case progress
    }
}

struct SpotProcessingStats: Decodable {
    let updatedAt: String?
    let processedRows: Int?
    let totalRows: Int?
    let elapsedSeconds: Int?
    let avgSecondsPerRow: Double?
    let threatRowsDetected: Int?
    let threatRate: Double?
    let projectedThreatRows: Int?
    let reviewRequiredRowsDetected: Int?
    let judgedRows: Int?

    private enum CodingKeys: String, CodingKey {
        case updatedAt = "updated_at"
        case processedRows = "processed_rows"
        case totalRows = "total_rows"
        case elapsedSeconds = "elapsed_seconds"
        case avgSecondsPerRow = "avg_seconds_per_row"
        case threatRowsDetected = "threat_rows_detected"
        case threatRate = "threat_rate"
        case projectedThreatRows = "projected_threat_rows"
        case reviewRequiredRowsDetected = "review_required_rows_detected"
        case judgedRows = "judged_rows"
    }

    init(
        updatedAt: String?,
        processedRows: Int?,
        totalRows: Int?,
        elapsedSeconds: Int?,
        avgSecondsPerRow: Double?,
        threatRowsDetected: Int?,
        threatRate: Double?,
        projectedThreatRows: Int?,
        reviewRequiredRowsDetected: Int?,
        judgedRows: Int?
    ) {
        self.updatedAt = updatedAt
        self.processedRows = processedRows
        self.totalRows = totalRows
        self.elapsedSeconds = elapsedSeconds
        self.avgSecondsPerRow = avgSecondsPerRow
        self.threatRowsDetected = threatRowsDetected
        self.threatRate = threatRate
        self.projectedThreatRows = projectedThreatRows
        self.reviewRequiredRowsDetected = reviewRequiredRowsDetected
        self.judgedRows = judgedRows
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        updatedAt = try container.decodeIfPresent(String.self, forKey: .updatedAt)
        processedRows = try container.decodeIfPresent(Int.self, forKey: .processedRows)
        totalRows = try container.decodeIfPresent(Int.self, forKey: .totalRows)
        elapsedSeconds = Self.decodeFlexibleInt(from: container, forKey: .elapsedSeconds)
        avgSecondsPerRow = try container.decodeIfPresent(Double.self, forKey: .avgSecondsPerRow)
        threatRowsDetected = try container.decodeIfPresent(Int.self, forKey: .threatRowsDetected)
        threatRate = try container.decodeIfPresent(Double.self, forKey: .threatRate)
        projectedThreatRows = try container.decodeIfPresent(Int.self, forKey: .projectedThreatRows)
        reviewRequiredRowsDetected = try container.decodeIfPresent(Int.self, forKey: .reviewRequiredRowsDetected)
        judgedRows = try container.decodeIfPresent(Int.self, forKey: .judgedRows)
    }

    private static func decodeFlexibleInt(
        from container: KeyedDecodingContainer<CodingKeys>,
        forKey key: CodingKeys
    ) -> Int? {
        if let intValue = try? container.decodeIfPresent(Int.self, forKey: key) {
            return intValue
        }
        if let doubleValue = try? container.decodeIfPresent(Double.self, forKey: key) {
            return Int(doubleValue.rounded())
        }
        if let stringValue = try? container.decodeIfPresent(String.self, forKey: key),
           let parsed = Double(stringValue) {
            return Int(parsed.rounded())
        }
        return nil
    }
}

struct SpotRunRecord: Decodable, Identifiable {
    let runID: String
    let state: String?
    let language: String?
    let reviewMode: String?
    let createdAt: Int?
    let updatedAt: Int?
    let reviewSummary: SpotRunReviewSummary?
    let progress: SpotRunProgress?
    let processingStats: SpotProcessingStats?

    var id: String { runID }

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case state
        case language
        case reviewMode = "review_mode"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case reviewSummary = "review_summary"
        case progress
        case processingStats = "processing_stats"
    }
}

struct SpotReviewRowPreview: Decodable, Identifiable {
    let rowIndex: Int
    let postText: String?
    let assignedCategory: String?
    let confidenceScore: Double?
    let reviewState: String?
    let reviewDecision: String?
    let explanation: String?
    let flags: [String]?

    var id: Int { rowIndex }

    private enum CodingKeys: String, CodingKey {
        case rowIndex = "row_index"
        case postText = "post_text"
        case assignedCategory = "assigned_category"
        case confidenceScore = "confidence_score"
        case reviewState = "review_state"
        case reviewDecision = "review_decision"
        case explanation
        case flags
    }
}

struct SpotReviewQueue: Decodable {
    let runID: String
    let state: String?
    let reviewSummary: SpotRunReviewSummary?
    let rows: [SpotReviewRowPreview]

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case state
        case reviewSummary = "review_summary"
        case rows
    }
}

struct SpotReviewEvidence: Decodable {
    let explanation: String?
    let flags: [String]
    let fallbackEvents: [String]
    let softSignalScore: Double?
    let softSignalFlags: [String]
    let softSignalEvidence: [String]

    private enum CodingKeys: String, CodingKey {
        case explanation
        case flags
        case fallbackEvents = "fallback_events"
        case softSignalScore = "soft_signal_score"
        case softSignalFlags = "soft_signal_flags"
        case softSignalEvidence = "soft_signal_evidence"
    }
}

struct SpotReviewControls: Decodable {
    let reviewState: String
    let reviewDecision: String?
    let reviewerNote: String

    private enum CodingKeys: String, CodingKey {
        case reviewState = "review_state"
        case reviewDecision = "review_decision"
        case reviewerNote = "reviewer_note"
    }
}

struct SpotReviewRowInspector: Decodable {
    let runID: String
    let rowIndex: Int
    let runState: String?
    let language: String?
    let reviewMode: String?
    let row: SpotReviewRowPreview
    let evidence: SpotReviewEvidence
    let reviewControls: SpotReviewControls

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case rowIndex = "row_index"
        case runState = "run_state"
        case language
        case reviewMode = "review_mode"
        case row
        case evidence
        case reviewControls = "review_controls"
    }
}

struct SpotRunDetail: Decodable {
    let runID: String
    let state: String
    let language: String?
    let reviewMode: String?
    let uploadID: String?
    let outputReady: Bool
    let updatedAt: Int?
    let progress: SpotRunProgress?
    let processingStats: SpotProcessingStats?
    let reviewSummary: SpotRunReviewSummary?
    let nextActions: [String]
    let availableOperations: SpotAvailableOperations?
    let recovery: SpotRecoveryState?
    let segmentSummary: SpotSegmentSummary?
    let signoff: SpotSignoffRecord?
    let reviewRowsPreview: [SpotReviewRowPreview]
    let artifacts: [SpotArtifactItem]

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case state
        case language
        case reviewMode = "review_mode"
        case uploadID = "upload_id"
        case outputReady = "output_ready"
        case updatedAt = "updated_at"
        case progress
        case processingStats = "processing_stats"
        case reviewSummary = "review_summary"
        case nextActions = "next_actions"
        case availableOperations = "available_operations"
        case recovery
        case segmentSummary = "segment_summary"
        case signoff
        case reviewRowsPreview = "review_rows_preview"
        case artifacts
    }
}

struct SpotSegmentSummary: Decodable {
    let totalSegments: Int?
    let processedRows: Int?
    let totalRows: Int?
    let segmentsByStatus: [String: Int]?
    let activeSegment: SpotActiveSegment?
    let completedSegments: Int?
    let progressPercentage: Double?
    let segmentProgressPercentage: Double?

    private enum CodingKeys: String, CodingKey {
        case totalSegments = "total_segments"
        case processedRows = "processed_rows"
        case totalRows = "total_rows"
        case segmentsByStatus = "segments_by_status"
        case activeSegment = "active_segment"
        case completedSegments = "completed_segments"
        case progressPercentage = "progress_percentage"
        case segmentProgressPercentage = "segment_progress_percentage"
    }
}

struct SpotActiveSegment: Decodable {
    let segmentID: String
    let segmentIndex: Int?
    let rowStart: Int?
    let rowEnd: Int?
    let rowCount: Int?
    let state: String?
    let processedRows: Int?

    private enum CodingKeys: String, CodingKey {
        case segmentID = "segment_id"
        case segmentIndex = "segment_index"
        case rowStart = "row_start"
        case rowEnd = "row_end"
        case rowCount = "row_count"
        case state
        case processedRows = "processed_rows"
    }
}

struct SpotRecoveryState: Decodable {
    let running: Bool
    let paused: Bool
    let pid: Int?
    let outputReady: Bool?
    let canRetry: Bool?
    let canCancel: Bool?
    let canResumeWorker: Bool?
    let pendingSegments: Int?
    let processingSegments: Int?
    let failedSegments: Int?

    private enum CodingKeys: String, CodingKey {
        case running
        case paused
        case pid
        case outputReady = "output_ready"
        case canRetry = "can_retry"
        case canCancel = "can_cancel"
        case canResumeWorker = "can_resume_worker"
        case pendingSegments = "pending_segments"
        case processingSegments = "processing_segments"
        case failedSegments = "failed_segments"
    }
}

struct SpotUploadQueueRun: Decodable {
    let runID: String?
    let state: String?
    let processedRows: Int?
    let totalRows: Int?
    let progressPercentage: Double?
    let rowProgressPercentage: Double?
    let estimatedRemainingSeconds: Int?
    let processingStats: SpotProcessingStats?

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case state
        case processedRows = "processed_rows"
        case totalRows = "total_rows"
        case progressPercentage = "progress_percentage"
        case rowProgressPercentage = "row_progress_percentage"
        case estimatedRemainingSeconds = "estimated_remaining_seconds"
        case processingStats = "processing_stats"
    }
}

struct SpotUploadQueueSummary: Decodable, Identifiable {
    let uploadID: String
    let status: String?
    let filename: String?
    let rowCount: Int?
    let segmentCount: Int?
    let segmentsByStatus: [String: Int]?
    let progressPercentage: Double?
    let rowProgressPercentage: Double?
    let segmentProgressPercentage: Double?
    let estimatedRemainingSeconds: Int?
    let processingStats: SpotProcessingStats?
    let run: SpotUploadQueueRun?

    var id: String { uploadID }

    private enum CodingKeys: String, CodingKey {
        case uploadID = "upload_id"
        case status
        case filename
        case rowCount = "row_count"
        case segmentCount = "segment_count"
        case segmentsByStatus = "segments_by_status"
        case progressPercentage = "progress_percentage"
        case rowProgressPercentage = "row_progress_percentage"
        case segmentProgressPercentage = "segment_progress_percentage"
        case estimatedRemainingSeconds = "estimated_remaining_seconds"
        case processingStats = "processing_stats"
        case run
    }
}

struct SpotOperationsOverview: Decodable {
    let uploads: Int
    let activeUploads: Int
    let totalSegments: Int
    let completedSegments: Int
    let totalRows: Int
    let processedRows: Int
    let progressPercentage: Double
    let segmentsByStatus: [String: Int]
    let recentUploads: [SpotUploadQueueSummary]

    private enum CodingKeys: String, CodingKey {
        case uploads
        case activeUploads = "active_uploads"
        case totalSegments = "total_segments"
        case completedSegments = "completed_segments"
        case totalRows = "total_rows"
        case processedRows = "processed_rows"
        case progressPercentage = "progress_percentage"
        case segmentsByStatus = "segments_by_status"
        case recentUploads = "recent_uploads"
    }
}

struct SpotAvailableOperations: Decodable {
    let pause: Bool
    let resume: Bool
    let cancel: Bool
    let retry: Bool
    let recover: Bool
}

struct SpotSignoffRecord: Decodable {
    let decision: String
    let note: String?
    let actor: String?
    let signedAt: Int?

    private enum CodingKeys: String, CodingKey {
        case decision
        case note
        case actor
        case signedAt = "signed_at"
    }
}

struct SpotArtifactItem: Decodable, Identifiable {
    let name: String
    let path: String
    let bytes: Int
    let purpose: String?
    let downloadPath: String?

    var id: String { name }

    private enum CodingKeys: String, CodingKey {
        case name
        case path
        case bytes
        case purpose
        case downloadPath = "download_path"
    }
}

struct SpotArtifactCenter: Decodable {
    let runID: String
    let state: String?
    let signoff: SpotSignoffRecord?
    let reviewSummary: SpotRunReviewSummary?
    let artifacts: [SpotArtifactItem]

    private enum CodingKeys: String, CodingKey {
        case runID = "run_id"
        case state
        case signoff
        case reviewSummary = "review_summary"
        case artifacts
    }
}

struct SpotUploadRecord: Decodable, Identifiable {
    let uploadID: String
    let filename: String?
    let storedPath: String?
    let status: String?
    let message: String?
    let rowCount: Int?
    let segmentCount: Int?

    var id: String { uploadID }

    private enum CodingKeys: String, CodingKey {
        case uploadID = "upload_id"
        case filename
        case storedPath = "stored_path"
        case status
        case message
        case rowCount = "row_count"
        case segmentCount = "segment_count"
    }
}

struct SpotRunStartResponse: Decodable {
    let status: String
    let runID: String
    let pid: Int?

    private enum CodingKeys: String, CodingKey {
        case status
        case runID = "run_id"
        case pid
    }
}

struct SpotOperationResponse: Decodable {
    let status: String
    let runID: String

    private enum CodingKeys: String, CodingKey {
        case status
        case runID = "run_id"
    }
}

struct SpotRuntimeSuspendResponse: Decodable {
    let status: String
    let count: Int
    let activeRuns: [SpotOperationResponse]

    private enum CodingKeys: String, CodingKey {
        case status
        case count
        case activeRuns = "active_runs"
    }
}

struct SpotRuntimeSummary {
    var healthDescription: String
    var reviewPending: Int
    var selectedRunID: String
    var runState: String
    var runLanguage: String
    var reviewMode: String
    var progressDescription: String
    var authenticatedAs: String
    var nextActions: [String]
    var outputReady: Bool

    static let empty = SpotRuntimeSummary(
        healthDescription: "No run summary yet.",
        reviewPending: 0,
        selectedRunID: "",
        runState: "-",
        runLanguage: "-",
        reviewMode: "-",
        progressDescription: "No active run selected.",
        authenticatedAs: "Native local mode",
        nextActions: [],
        outputReady: false
    )
}

struct SpotHistoricalBaseline {
    let avgSecondsPerRow: Double?
    let reviewRequiredRate: Double?
    let threatRate: Double?

    static let empty = SpotHistoricalBaseline(
        avgSecondsPerRow: nil,
        reviewRequiredRate: nil,
        threatRate: nil
    )
}

struct SpotNativeConfig {
    var pythonBin: String
    var runsDir: String
    var logsDir: String
    var accessCode: String
    var lockedSSOTPath: String
    var port: Int
    var intakeWatchDir: String
    var intakeArchiveDir: String
    var intakeFailedDir: String
    var autoStartWatchFolder: Bool

    static let empty = SpotNativeConfig(
        pythonBin: "",
        runsDir: "",
        logsDir: "",
        accessCode: "",
        lockedSSOTPath: "",
        port: 8765,
        intakeWatchDir: "",
        intakeArchiveDir: "",
        intakeFailedDir: "",
        autoStartWatchFolder: true
    )
}

struct SpotReviewDraft {
    var reviewState: String
    var reviewDecision: String
    var reviewerNote: String

    static let empty = SpotReviewDraft(reviewState: "pending", reviewDecision: "", reviewerNote: "")
}

struct SpotInboxDocumentEvent: Codable, Identifiable {
    let id: String
    let stage: String
    let note: String
    let createdAt: TimeInterval
    let uploadID: String?
    let runID: String?
    let destinationPath: String?
}

struct SpotInboxDocumentActivity: Codable, Identifiable {
    let id: String
    var filename: String
    var sourcePath: String
    var sourceBytes: UInt64
    var stage: String
    var note: String
    var uploadID: String?
    var runID: String?
    var destinationPath: String?
    var detectedAt: TimeInterval
    var updatedAt: TimeInterval
    var events: [SpotInboxDocumentEvent]
}
