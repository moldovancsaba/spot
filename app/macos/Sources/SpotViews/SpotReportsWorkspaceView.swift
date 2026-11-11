import SwiftUI

struct SpotReportsWorkspaceView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack {
                    VStack(alignment: .leading) {
                        Text("Reports").font(.largeTitle).bold()
                        Text("Automatic AI reports, model findings, and human-confirmed reports.").foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh reports") { Task { await service.loadRunReports() } }
                }
                Picker("Run", selection: Binding(get: { service.selectedRunID }, set: { value in Task { await service.selectRun(value); await service.loadRunReports() } })) {
                    ForEach(service.availableRuns) { run in Text(run.runID).tag(run.runID) }
                }
                if let reports = service.runReports {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 180))], alignment: .leading, spacing: 16) {
                        countCard("Classified posts", reports.summary.total)
                        countCard("Automatic complete", reports.summary.automatic)
                        countCard("Automatic checks pending", reports.summary.automaticPending)
                        countCard("Confirmed threats", reports.summary.confirmedThreats)
                        countCard("Not antisemitic", reports.summary.falseAlarms)
                        countCard("Needs human action", reports.summary.unresolved)
                        countCard("AI reports", reports.summary.reporting)
                    }
                    if let evaluation = reports.evaluation {
                        GroupBox("Evaluation report") {
                            VStack(alignment: .leading, spacing: 12) {
                                Text(String(format: "%.1f%% agreement with reference labels", evaluation.referenceAgreementPercent)).font(.title2).bold()
                                Text("\(evaluation.matchesReference) of \(evaluation.sampleRows) reference labels matched. This is a labelled sample comparison, not a certification of accuracy.")
                                HStack {
                                    Text("Failed analysis: \(evaluation.failedAnalysisRows)")
                                    Text("Missing output: \(evaluation.missingOutputRows)")
                                    if let f1 = evaluation.macroF1 { Text(String(format: "Macro F1: %.4f", f1)) }
                                }.foregroundStyle(.secondary)
                                if let categories = evaluation.perCategory {
                                    ForEach(categories.keys.sorted(), id: \.self) { key in
                                        if let metric = categories[key] {
                                            HStack { Text(key); Spacer(); Text("\(metric.correct) / \(metric.support) matched") }
                                        }
                                    }
                                }
                                ForEach(evaluation.limitations ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                            }.padding(8).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    } else {
                        Text("Any positive analysis at 30% or above generates an unconfirmed AI report. Other unresolved cases appear in the Review queue.").foregroundStyle(.secondary)
                    }
                    GroupBox("Automatic AI finding reports - unconfirmed") {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Any positive antisemitism analysis >=30% category confidence triggers a PDF without human review, even if other analyses disagree. This score is not a calibrated probability of harm. Saved human decisions take precedence.").foregroundStyle(.secondary)
                            if (reports.automaticExports ?? []).isEmpty { Text("No automatic AI finding reports generated yet.").foregroundStyle(.secondary) }
                            ForEach(reports.automaticExports ?? []) { report in
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text("Row \(report.rowIndex) · AI-generated / unconfirmed").font(.headline)
                                        Text("\(Date(timeIntervalSince1970: Double(report.createdAt)).formatted()) · \(report.isCurrent == 1 ? "Current" : "Superseded")").font(.caption)
                                    }
                                    Spacer()
                                    Button("Save AI report PDF") { Task { await service.saveAutomaticReport(rowIndex:report.rowIndex,reportID:report.reportID) } }
                                        .disabled(report.isCurrent != 1 || service.exportingThreatReport)
                                }
                            }
                            Text("Latest 100 exports. All current reporting cases are available in the AI reports bucket.").font(.caption).foregroundStyle(.secondary)
                        }.padding(8).frame(maxWidth:.infinity,alignment:.leading)
                    }
                    GroupBox("Human-confirmed threat reports") {
                        VStack(alignment: .leading, spacing: 12) {
                            if (reports.exports ?? []).isEmpty {
                                Text("No threat reports exported yet. Confirm a threat in its case review, then export the official PDF.").foregroundStyle(.secondary)
                            }
                            ForEach(reports.exports ?? []) { report in
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text("Row \(report.rowIndex) · \(report.reportID)").font(.headline)
                                        Text("\(report.actor) · \(Date(timeIntervalSince1970: Double(report.createdAt)).formatted())").font(.caption)
                                        Text(report.isCurrent == 1 ? "Current confirmation" : "Superseded - retained in audit history").font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Button("Save PDF") { Task { await service.openStoredThreatReport(reportID: report.reportID) } }
                                        .disabled(report.isCurrent != 1 || !service.canExportThreatReports || service.exportingThreatReport)
                                }
                            }
                        }.padding(8).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    GroupBox("Case decisions") {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Automatically processed posts need no action. Open Review for exceptions or optionally inspect any result. Human-confirmed PDFs require a saved human confirmation; AI finding PDFs are generated automatically at the 30% threshold.").foregroundStyle(.secondary)
                            ForEach(service.reviewQueueRows) { row in
                                HStack(alignment: .top, spacing: 18) {
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text("Row \(row.rowIndex) · \(row.assignedCategory ?? "No model category")").font(.headline)
                                        Text(row.postText ?? "").lineLimit(2).foregroundStyle(.secondary)
                                        Text(outcomeLabel(row.outcome)).font(.caption).bold()
                                        if let humanCategory = row.humanCategory { Text("Reviewed category: \(humanCategory)").font(.caption) }
                                    }
                                    Spacer()
                                    Button(row.workflowBucket == "automatic_pending" ? "View automatic checks" : "Review case") {
                                        Task { await service.openCaseForReview(row) }
                                    }
                                    if let report = row.automaticReport {
                                        Button("Save AI report PDF") { Task { await service.saveAutomaticReport(rowIndex:row.rowIndex,reportID:report.reportID) } }.disabled(service.exportingThreatReport)
                                    }
                                    if row.outcome == "confirmed_threat" {
                                        Button("Export threat PDF") { Task { await service.exportConfirmedThreatPDF(rowIndex: row.rowIndex) } }
                                            .disabled(!service.canExportThreatReports || service.exportingThreatReport)
                                    }
                                }.padding(.vertical, 8)
                                Divider()
                            }
                            HStack {
                                Button("Previous") { Task { await service.changeCasePage(-1) } }.disabled(service.casePageOffset == 0)
                                Text("\(min(service.casePageOffset + 1, service.casePageTotal))-\(min(service.casePageOffset + 100, service.casePageTotal)) of \(service.casePageTotal)")
                                Button("Next") { Task { await service.changeCasePage(1) } }.disabled(service.casePageOffset + 100 >= service.casePageTotal)
                            }
                        }.padding(8)
                    }
                } else {
                    ContentUnavailableView("Choose a run", systemImage: "doc.text", description: Text("Select a run to see its reports and case decisions."))
                }
                if !service.reportMessage.isEmpty { Text(service.reportMessage).foregroundStyle(.secondary) }
            }.padding(16)
        }.task(id: service.selectedRunID) { await service.loadRunReports() }
    }

    private func countCard(_ title: String, _ count: Int) -> some View {
        VStack(alignment: .leading, spacing: 8) { Text(title).foregroundStyle(.secondary); Text("\(count)").font(.largeTitle).bold() }
            .padding(18).frame(maxWidth: .infinity, alignment: .leading)
            .background(.quaternary, in: RoundedRectangle(cornerRadius: 14))
    }

    private func outcomeLabel(_ outcome: String?) -> String {
        switch outcome { case "confirmed_threat": "Confirmed threat"; case "false_alarm": "Not antisemitic"; case "ai_reported": "AI report generated / unconfirmed - no review required"; case "automatic_pending": "Automatic checks pending — no action needed"; case "automatic": "Processed automatically — no review needed"; default: "Awaiting human decision" }
    }
}
