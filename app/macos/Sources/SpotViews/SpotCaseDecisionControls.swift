import SwiftUI

@MainActor
final class SpotHumanCaseDraft: ObservableObject {
    @Published var category = ""
    @Published var note = ""
    @Published var token = ""
    @Published var saving = false
}

struct SpotCaseDecisionControls: View {
    @ObservedObject var service: SpotCoreService
    let inspector: SpotReviewRowInspector
    @StateObject private var draft = SpotHumanCaseDraft()
    private let categories = ["Anti-Israel", "Anti-Judaism", "Classical Antisemitism", "Structural Antisemitism", "Conspiracy Theories"]

    var body: some View {
        GroupBox(inspector.caseReview?.automaticReport == nil ? "Human decision" : "Automatic reporting") {
            VStack(alignment: .leading, spacing: 14) {
                if let record = inspector.caseReview {
                    Text(record.label).font(.title3).bold()
                    if let report = record.automaticReport {
                        Text("No review is required. At least one positive analysis reached 30% category confidence. The automatically generated PDF is an unconfirmed AI finding, not a human decision.").foregroundStyle(.secondary)
                        ForEach(Array(report.findings.enumerated()), id: \.offset) { _, finding in
                            Text("\(finding.category) · \(String(format: "%.0f%%",finding.confidence * 100)) · \(finding.stage) · \(finding.model)").font(.caption)
                        }
                        Button(report.state == "generated" ? "Save automatic AI report PDF" : "Generate / retry AI report PDF") { Task { await service.saveAutomaticReport(rowIndex: inspector.rowIndex,reportID:report.reportID) } }
                            .disabled(service.exportingThreatReport)
                        if let error = report.lastError { Text("PDF generation needs retry: \(error)").foregroundStyle(.orange) }
                    } else if record.outcome == "automatic_pending" {
                        Text("No action is needed. Automatic checks are still pending or running. This case will appear in Needs your review only if those checks cannot resolve it. The earlier analysis is shown below for reference.").foregroundStyle(.secondary)
                    } else if record.outcome == "automatic" {
                        Text("No action is required. The model result is recorded automatically. You may optionally override it.").foregroundStyle(.secondary)
                    } else if let reasons = record.reviewReasons, !reasons.isEmpty, record.decisionID == nil {
                        Text("Why this needs review: " + Array(Set(reasons.map { reviewReason($0) })).sorted().joined(separator: ", "))
                            .foregroundStyle(.orange)
                    }
                    ForEach(record.automaticChecks ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                    if let history = record.analysisHistory, !history.isEmpty {
                        DisclosureGroup("Earlier analyses retained (\(history.count))") {
                            ForEach(history) { revision in
                                VStack(alignment: .leading, spacing: 5) {
                                    Text("Previous: \(revision.previousCategory) → Current: \(revision.newCategory)")
                                    Text("Previous warnings: \(revision.previousFlags.joined(separator: ", "))").font(.caption)
                                    Text("Current warnings: \(revision.newFlags.joined(separator: ", "))").font(.caption)
                                }.padding(.vertical, 6)
                            }
                        }
                    }
                    if let humanCategory = record.humanCategory { Text("Reviewed category: \(humanCategory)") }
                    if let reviewer = record.reviewer, let timestamp = record.reviewedAt {
                        Text("Saved by \(reviewer) · \(Date(timeIntervalSince1970: Double(timestamp)).formatted())").font(.caption).foregroundStyle(.secondary)
                    }
                    if record.decisionStale || draft.token != record.caseToken {
                        Text("This case changed. Refresh it and review the evidence before deciding.").foregroundStyle(.orange)
                    }
                    if record.automaticReport != nil {
                        Divider()
                        Text("Optional human correction").font(.headline)
                        if !service.canReviewCases { SettingsLink { Text("Reviewer access for optional corrections") } }
                    }
                    if !service.canReviewCases && record.outcome != "automatic_pending" && record.outcome != "ai_reported" {
                        HStack { Text("Choose Reviewer or Administrator in Settings to save a decision."); SettingsLink { Text("Reviewer access") } }
                    }
                    Picker("Threat category", selection: $draft.category) {
                        Text("Choose a threat category").tag("")
                        ForEach(categories, id: \.self) { Text($0).tag($0) }
                    }
                    .disabled(record.outcome == "automatic_pending")
                    .onChange(of: draft.category) { _, _ in updateDraftDirty() }
                    Text("Review note").font(.headline)
                    TextEditor(text: $draft.note).frame(minHeight: 110).disabled(record.outcome == "automatic_pending")
                        .onChange(of: draft.note) { _, _ in updateDraftDirty() }
                    Text("The original model proposal stays in the evidence. Your saved decision moves this case to its bucket and opens the next waiting case.").font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Button("Confirm threat") { save("confirmed_threat") }
                            .buttonStyle(.borderedProminent).tint(.teal).disabled(draft.category.isEmpty || !canSave)
                        Button("Not antisemitic") { save("false_alarm") }.disabled(!canSave)
                        Button("Needs follow-up") { save("unresolved") }.disabled(!canSave)
                        Button("Refresh case") { Task {
                            let note = draft.note; let category = draft.category; let dirty = service.reviewNoteIsDirty
                            await service.loadReviewInspector(rowIndex: inspector.rowIndex); reloadDraft()
                            if dirty { draft.note = note; draft.category = category; service.reviewNoteIsDirty = true }
                        } }.disabled(draft.saving)
                    }
                    Divider()
                    Button("Export human-confirmed {spot} threat PDF") { Task { await service.exportConfirmedThreatPDF(rowIndex: inspector.rowIndex) } }
                        .disabled(!record.canExport || draft.category != record.humanCategory || draft.note != record.decisionNote || draft.token != record.caseToken || !service.canExportThreatReports || service.exportingThreatReport)
                    if record.canExport && (draft.note != record.decisionNote || draft.category != record.humanCategory) { Text("Save your decision changes before exporting.").font(.caption).foregroundStyle(.secondary) }
                    if !record.canExport { Text("Human-confirmed PDF export is separate from automatic, unconfirmed AI reports.").font(.caption).foregroundStyle(.secondary) }
                    if !service.reviewSaveMessage.isEmpty { Text(service.reviewSaveMessage).foregroundStyle(.secondary) }
                } else {
                    Text("Case decisions are not available yet. Refresh the case after the runtime is updated.")
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(8)
        }.disabled(draft.saving || service.savingCaseDecision)
            .onAppear { reloadDraft() }
            .onChange(of: "\(inspector.runID):\(inspector.rowIndex)") { _, _ in reloadDraft() }
    }

    private func reviewReason(_ reason: String) -> String {
        switch reason {
        case "LOW_CONFIDENCE": "The classification is uncertain"
        case "SOFT_SIGNAL_REVIEW": "Possible indirect antisemitism needs context"
        case "SECOND_PASS_DISAGREEMENT", "SECOND_PASS_CATEGORY_OVERRIDDEN": "The models disagreed"
        case "SECOND_PASS_JUDGE_FAIL", "SECOND_PASS_JUDGE_REVIEW", "JUDGE_REVIEW": "The quality check could not approve the result"
        case "SECOND_PASS_ALT_ROUTE": "A second analysis was needed"
        case "INVALID_MODEL_METADATA", "UNSTRUCTURED_MODEL_OUTPUT": "The model returned an incomplete or unreliable response"
        case "EMPTY_TEXT", "SKIPPED": "There is no usable post text"
        case "DRAFTER_CONTENT_CHANGED", "DRAFTER_OUTPUT_REJECTED": "The analysis input could not be verified"
        case "REVIEW_MODE_REQUESTED": "This run requested manual review"
        default: "Analysis needs checking (\(reason.replacingOccurrences(of: "_", with: " ").lowercased()))"
        }
    }

    private var canSave: Bool { inspector.caseReview?.outcome != "automatic_pending" && service.canReviewCases && service.selectedReviewRowIndex == inspector.rowIndex && service.selectedRunID == inspector.runID && !draft.saving && !service.savingCaseDecision && draft.token == inspector.caseReview?.caseToken }

    private func updateDraftDirty() {
        let saved = inspector.caseReview?.humanCategory ?? inspector.row.assignedCategory ?? ""
        let originalCategory = categories.contains(saved) ? saved : ""
        service.reviewNoteIsDirty = draft.note != (inspector.caseReview?.decisionNote ?? "") || draft.category != originalCategory
    }

    private func reloadDraft() {
        let current = service.activeReviewInspector.flatMap { $0.runID == inspector.runID && $0.rowIndex == inspector.rowIndex ? $0 : nil } ?? inspector
        let savedCategory = current.caseReview?.humanCategory ?? current.row.assignedCategory ?? ""
        draft.category = categories.contains(savedCategory) ? savedCategory : ""
        draft.note = current.caseReview?.decisionNote ?? ""
        draft.token = current.caseReview?.caseToken ?? ""
        service.reviewNoteIsDirty = false
    }

    private func save(_ outcome: String) {
        draft.saving = true
        Task {
            let rowIndex = inspector.rowIndex
            if await service.saveCaseOutcome(outcome, category: draft.category, note: draft.note, token: draft.token),
               service.activeReviewInspector?.rowIndex == rowIndex { reloadDraft() }
            draft.saving = false
        }
    }
}
