import Foundation

struct SpotCaseRecord: Decodable {
    let caseToken: String
    let outcome: String
    let humanCategory: String?
    let reviewer: String?
    let reviewedAt: Int?
    let decisionID: String?
    let decisionNote: String
    let canExport: Bool
    let decisionStale: Bool
    let reviewReasons: [String]?
    let automaticChecks: [String]?
    let analysisHistory: [SpotAnalysisRevision]?
    let automaticReport: SpotAutomaticReport?
    enum CodingKeys: String, CodingKey {
        case caseToken = "case_token", outcome, humanCategory = "human_category", reviewer
        case reviewedAt = "reviewed_at", decisionID = "decision_id", decisionNote = "decision_note"
        case canExport = "can_export", decisionStale = "decision_stale", reviewReasons = "review_reasons"
        case automaticChecks = "automatic_checks", analysisHistory = "analysis_history", automaticReport = "automatic_report"
    }
    var label: String {
        switch outcome {
        case "ai_reported": "Automatic AI report - unconfirmed"
        case "automatic_pending": "Automatic checks pending"
        case "automatic": "Processed automatically — no review needed"
        case "confirmed_threat": "Confirmed threat"
        case "false_alarm": "Not antisemitic"
        default: decisionID == nil ? "Needs your review" : "Needs follow-up"
        }
    }
}

struct SpotCasePage: Decodable {
    let total: Int
    let offset: Int
    let rows: [SpotReviewRowPreview]
    let counts: SpotReviewBucketCounts
    let recheck: SpotAutomaticRecheck?
}

struct SpotCaseSummary: Decodable {
    let total: Int
    let confirmedThreats: Int
    let falseAlarms: Int
    let unresolved: Int
    let automatic: Int
    let automaticPending: Int
    let reporting: Int
    let failedAnalysis: Int
    enum CodingKeys: String, CodingKey {
        case total, automatic, reporting, confirmedThreats = "confirmed_threats", falseAlarms = "false_alarms", unresolved
        case failedAnalysis = "failed_analysis", automaticPending = "automatic_pending"
    }
}

struct SpotEvaluationCategory: Decodable {
    let support: Int
    let correct: Int
    let precision: Double?
    let recall: Double?
    let f1: Double
}

struct SpotEvaluationReport: Decodable {
    let sampleRows: Int
    let matchesReference: Int
    let referenceAgreementPercent: Double
    let failedAnalysisRows: Int
    let missingOutputRows: Int
    let macroF1: Double?
    let perCategory: [String: SpotEvaluationCategory]?
    let limitations: [String]?
    enum CodingKeys: String, CodingKey {
        case sampleRows = "sample_rows", matchesReference = "matches_reference"
        case referenceAgreementPercent = "reference_agreement_percent", failedAnalysisRows = "failed_analysis_rows"
        case missingOutputRows = "missing_output_rows", macroF1 = "macro_f1", perCategory = "per_category", limitations
    }
}

struct SpotRunReports: Decodable {
    let summary: SpotCaseSummary
    let evaluation: SpotEvaluationReport?
    let exports: [SpotThreatReportExport]?
    let automaticExports: [SpotAutomaticReportExport]?
    enum CodingKeys: String, CodingKey { case summary, evaluation, exports, automaticExports = "automatic_exports" }
}

struct SpotThreatReportExport: Decodable, Identifiable {
    let reportID: String
    let rowIndex: Int
    let createdAt: Int
    let actor: String
    let isCurrent: Int
    var id: String { reportID }
    enum CodingKeys: String, CodingKey {
        case reportID = "report_id", rowIndex = "row_index", createdAt = "created_at", actor, isCurrent = "is_current"
    }
}

struct SpotReviewBucketCounts: Decodable {
    let total: Int
    let waiting: Int
    let followUp: Int
    let confirmedThreat: Int
    let falseAlarm: Int
    let automatic: Int
    let automaticPending: Int
    let reporting: Int
    static let empty = SpotReviewBucketCounts(total: 0, waiting: 0, followUp: 0, confirmedThreat: 0, falseAlarm: 0, automatic: 0, automaticPending: 0, reporting: 0)
    var reviewed: Int { followUp + confirmedThreat + falseAlarm }
    func count(_ bucket: String) -> Int {
        switch bucket { case "waiting": waiting; case "follow_up": followUp; case "confirmed_threat": confirmedThreat; case "false_alarm": falseAlarm; case "automatic": automatic; case "automatic_pending": automaticPending; case "reporting": reporting; default: total }
    }
    enum CodingKeys: String, CodingKey {
        case total, waiting, automatic, reporting, automaticPending = "automatic_pending", followUp = "follow_up", confirmedThreat = "confirmed_threat", falseAlarm = "false_alarm"
    }
}

struct SpotAutomaticRecheck: Decodable {
    let state: String
    let total: Int
    let processed: Int
    let resolved: Int
    let remaining: Int
}
struct SpotAnalysisRevision: Decodable, Identifiable {
    let revisionID: String
    let previousCategory: String
    let newCategory: String
    let previousFlags: [String]
    let newFlags: [String]
    var id: String { revisionID }
    enum CodingKeys: String, CodingKey {
        case revisionID = "revision_id", previousCategory = "previous_category", newCategory = "new_category"
        case previousFlags = "previous_flags", newFlags = "new_flags"
    }
}

struct SpotAutomaticFinding: Decodable {
    let stage: String
    let model: String
    let category: String
    let confidence: Double
}
struct SpotAutomaticReport: Decodable {
    let reportID: String?
    let state: String
    let lastError: String?
    let findings: [SpotAutomaticFinding]
    enum CodingKeys: String,CodingKey { case reportID = "report_id",state,lastError = "last_error",findings }
}
struct SpotAutomaticReportExport: Decodable,Identifiable {
    let reportID: String
    let rowIndex: Int
    let createdAt: Int
    let isCurrent: Int
    var id: String { reportID }
    enum CodingKeys: String,CodingKey { case reportID = "report_id",rowIndex = "row_index",createdAt = "created_at",isCurrent = "is_current" }
}
