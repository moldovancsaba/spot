import SwiftUI

struct SpotReviewWorkspaceView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        HSplitView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Review queue")
                            .font(.title2)
                            .fontWeight(.semibold)
                        Text(service.selectedRunID.isEmpty ? "No run selected" : "Run \(service.selectedRunID)")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh Queue") {
                        Task { await service.loadReviewQueueForSelectedRun() }
                    }
                    .disabled(service.selectedRunID.isEmpty)
                }

                Picker("Run", selection: Binding(get: { service.selectedRunID }, set: { value in Task { await service.selectRun(value) } })) {
                    ForEach(service.availableRuns) { run in Text(run.runID).tag(run.runID) }
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text("Needs your review: \(service.reviewBucketCounts.waiting) · Automatic checks pending: \(service.reviewBucketCounts.automaticPending) · Human decisions: \(service.reviewBucketCounts.reviewed) · Automatic: \(service.reviewBucketCounts.automatic)")
                        .font(.headline)
                    Text("Cases with any positive analysis >=30% go directly to AI reports. Only other unresolved cases need your review. Oldest waiting first.").font(.caption).foregroundStyle(.secondary)
                    if let recheck = service.automaticRecheck, recheck.state != "completed" {
                        Text("Automatic recheck: \(recheck.processed) / \(recheck.total) · \(recheck.resolved) resolved · Unreported unfinished cases stay in Automatic checks pending")
                            .font(.callout).foregroundStyle(.teal)
                    }
                    Picker("Bucket", selection: Binding(get: { service.reviewBucket }, set: { bucket in Task { await service.selectReviewBucket(bucket) } })) {
                        Text("Needs your review (\(service.reviewBucketCounts.waiting))").tag("waiting")
                        Text("Needs follow-up (\(service.reviewBucketCounts.followUp))").tag("follow_up")
                        Text("Confirmed threats (\(service.reviewBucketCounts.confirmedThreat))").tag("confirmed_threat")
                        Text("Not antisemitic (\(service.reviewBucketCounts.falseAlarm))").tag("false_alarm")
                        Text("Automatic checks pending (\(service.reviewBucketCounts.automaticPending))").tag("automatic_pending")
                        Text("Automatic complete (\(service.reviewBucketCounts.automatic))").tag("automatic")
                        Text("AI reports (\(service.reviewBucketCounts.reporting))").tag("reporting")
                    }.pickerStyle(.menu)
                    if !service.reviewSaveMessage.isEmpty { Text(service.reviewSaveMessage).font(.callout).textSelection(.enabled) }
                }
                HStack {
                    Button("Previous") { Task { await service.changeCasePage(-1) } }.disabled(service.casePageOffset == 0)
                    Text("\(min(service.casePageOffset + 1, service.casePageTotal))-\(min(service.casePageOffset + 100, service.casePageTotal)) / \(service.casePageTotal)").font(.caption)
                    Button("Next") { Task { await service.changeCasePage(1) } }.disabled(service.casePageOffset + 100 >= service.casePageTotal)
                }
                if service.reviewQueueRows.isEmpty {
                    ContentUnavailableView(
                        service.reviewBucket == "waiting" ? "You’re caught up" : "No cases in this bucket",
                        systemImage: "checkmark.seal",
                        description: Text(service.reviewBucket == "waiting" ? "No cases need your review right now. Unfinished automatic checks are in their own bucket; only unresolved results will arrive here. Follow-up cases are in their own bucket." : (service.reviewBucket == "automatic_pending" ? "No automatic checks are pending for saved cases." : "Cases will appear here after their checks or your decision are saved."))
                    )
                } else {
                    List(service.reviewQueueRows, selection: Binding(
                        get: { service.selectedReviewRowIndex },
                        set: { rowIndex in
                            if let rowIndex {
                                Task { await service.loadReviewInspector(rowIndex: rowIndex) }
                            }
                        }
                    )) { row in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text("Row \(row.rowIndex)")
                                    .font(.headline)
                                Spacer()
                                Text(row.workflowBucket == "reporting" ? "AI report - no review required" : row.workflowBucket == "automatic_pending" ? "Automatic checks pending — no action needed" : row.workflowBucket == "automatic" ? "Automatic — no review needed" : row.workflowBucket == "follow_up" ? "Needs follow-up" : (row.outcome == "confirmed_threat" ? "Confirmed threat" : (row.outcome == "false_alarm" ? "Not antisemitic" : "Needs your review")))
                                    .foregroundStyle(.secondary)
                            }
                            if let category = row.assignedCategory, !category.isEmpty {
                                Text("Model: \(category)")
                            }
                            if let humanCategory = row.humanCategory { Text("Human: \(humanCategory)").font(.caption).bold() }
                            if let postText = row.postText, !postText.isEmpty {
                                Text(postText)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(2)
                            }
                        }
                        .padding(.vertical, 4)
                        .tag(row.rowIndex)
                    }
                    .listStyle(.sidebar)
                }
            }
            .frame(minWidth: 320)
            .padding(20)
            .disabled(service.savingCaseDecision)

            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let inspector = service.activeReviewInspector {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Row \(inspector.rowIndex)")
                                    .font(.title2)
                                    .fontWeight(.semibold)
                                Text("\(inspector.runState ?? "-") · \(inspector.language ?? "-") · \(inspector.reviewMode ?? "-")")
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                        }

                        GroupBox("Post") {
                            VStack(alignment: .leading, spacing: 8) {
                                if let category = inspector.row.assignedCategory, !category.isEmpty {
                                    Text("Model proposal: \(category)")
                                }
                                if let score = inspector.row.confidenceScore {
                                    Text(String(format: "Model-reported score: %.3f", score))
                                        .foregroundStyle(.secondary)
                                }
                                Text(inspector.row.postText ?? "No post text available.")
                                    .textSelection(.enabled)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        GroupBox("Evidence") {
                            VStack(alignment: .leading, spacing: 10) {
                                if let explanation = inspector.evidence.explanation, !explanation.isEmpty {
                                    Text(explanation)
                                        .textSelection(.enabled)
                                }
                                if !inspector.evidence.flags.isEmpty {
                                    Text("Original analysis flags: \(inspector.evidence.flags.joined(separator: ", "))")
                                }
                                if !inspector.evidence.fallbackEvents.isEmpty {
                                    Text("Fallback Events: \(inspector.evidence.fallbackEvents.joined(separator: ", "))")
                                }
                                if let softSignalScore = inspector.evidence.softSignalScore {
                                    Text(String(format: "Soft Signal Score: %.3f", softSignalScore))
                                }
                                if !inspector.evidence.softSignalFlags.isEmpty {
                                    Text("Soft Signal Flags: \(inspector.evidence.softSignalFlags.joined(separator: ", "))")
                                }
                                if !inspector.evidence.softSignalEvidence.isEmpty {
                                    Text("Soft Signal Evidence: \(inspector.evidence.softSignalEvidence.joined(separator: " | "))")
                                        .textSelection(.enabled)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }

                        SpotCaseDecisionControls(service: service, inspector: inspector)
                    } else {
                        ContentUnavailableView(
                            "No row selected",
                            systemImage: "doc.text.magnifyingglass",
                            description: Text("Choose a bucket to inspect saved decisions. The next waiting case opens automatically.")
                        )
                    }
                }
                .padding(20)
            }
            .frame(minWidth: 560)
        }
        .frame(minWidth: 1080, minHeight: 760)
        .task { await service.loadReviewQueueForSelectedRun() }
    }
}
