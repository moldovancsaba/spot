import SwiftUI

struct SpotReviewWorkspaceView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        HSplitView {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Review Queue")
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

                if service.reviewQueueRows.isEmpty {
                    ContentUnavailableView(
                        "No flagged rows",
                        systemImage: "checkmark.seal",
                        description: Text("The selected run has no queued review rows or they have not been loaded yet.")
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
                                Text(row.reviewState ?? "pending")
                                    .foregroundStyle(.secondary)
                            }
                            if let category = row.assignedCategory, !category.isEmpty {
                                Text(category)
                            }
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
                                    Text("Category: \(category)")
                                }
                                if let score = inspector.row.confidenceScore {
                                    Text(String(format: "Confidence: %.3f", score))
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
                                    Text("Flags: \(inspector.evidence.flags.joined(separator: ", "))")
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

                        GroupBox("Reviewer Controls") {
                            VStack(alignment: .leading, spacing: 12) {
                                Picker("Review State", selection: $service.reviewDraft.reviewState) {
                                    Text("pending").tag("pending")
                                    Text("reviewed").tag("reviewed")
                                    Text("escalated").tag("escalated")
                                }
                                .pickerStyle(.segmented)

                                Picker("Decision", selection: $service.reviewDraft.reviewDecision) {
                                    Text("none").tag("")
                                    Text("confirm").tag("confirm")
                                    Text("adjust").tag("adjust")
                                    Text("skip").tag("skip")
                                }
                                .pickerStyle(.menu)

                                Text("Reviewer Note")
                                    .font(.headline)
                                TextEditor(text: $service.reviewDraft.reviewerNote)
                                    .frame(minHeight: 120)
                                    .font(.body)

                                HStack {
                                    Button("Save Review") {
                                        Task { await service.saveActiveReview() }
                                    }
                                    if !service.reviewSaveMessage.isEmpty {
                                        Text(service.reviewSaveMessage)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    } else {
                        ContentUnavailableView(
                            "No row selected",
                            systemImage: "doc.text.magnifyingglass",
                            description: Text("Pick a flagged row to inspect its evidence and save a review decision.")
                        )
                    }
                }
                .padding(20)
            }
            .frame(minWidth: 560)
        }
        .frame(minWidth: 1080, minHeight: 760)
    }
}
