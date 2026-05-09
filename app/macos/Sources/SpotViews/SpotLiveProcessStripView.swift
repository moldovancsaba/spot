import SwiftUI

struct SpotLiveProcessStripView: View {
    @ObservedObject var service: SpotCoreService

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("LIVE RUN")
                    .font(.headline)
                    .tracking(1.2)
                    .foregroundStyle(.teal)
                Spacer()
                if !service.selectedRunID.isEmpty {
                    Text(service.selectedRunID)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            }

            if service.hasVisibleActiveRun {
                LazyVGrid(columns: compactColumns, spacing: 10) {
                    compactMetric(
                        title: "State",
                        value: service.activeRunSummary.runState,
                        detail: service.activeRunSummary.runLanguage == "-" ? service.activeRunSummary.reviewMode : "\(service.activeRunSummary.runLanguage) · \(service.activeRunSummary.reviewMode)",
                        tint: stateTint(service.activeRunSummary.runState)
                    )
                    compactMetric(
                        title: "Processed",
                        value: formattedInt(service.activeRunProcessedRows),
                        detail: "of \(formattedInt(service.activeRunTotalRows))",
                        tint: .primary
                    )
                    compactMetric(
                        title: "Progress",
                        value: formattedPercent(service.activeRunProgressPercentage),
                        detail: "row completion",
                        tint: .primary
                    )
                    compactMetric(
                        title: "Avg sec/row",
                        value: formattedDecimal(service.activeRunProcessingStats?.avgSecondsPerRow),
                        detail: deltaText(
                            current: service.activeRunProcessingStats?.avgSecondsPerRow,
                            baseline: service.historicalBaseline.avgSecondsPerRow,
                            percentage: false
                        ),
                        tint: deviationTint(
                            current: service.activeRunProcessingStats?.avgSecondsPerRow,
                            baseline: service.historicalBaseline.avgSecondsPerRow
                        )
                    )
                    compactMetric(
                        title: "Review rate",
                        value: formattedRatioPercent(service.activeReviewRequiredRate),
                        detail: deltaText(
                            current: service.activeReviewRequiredRate,
                            baseline: service.historicalBaseline.reviewRequiredRate,
                            percentage: true
                        ),
                        tint: deviationTint(
                            current: service.activeReviewRequiredRate,
                            baseline: service.historicalBaseline.reviewRequiredRate
                        )
                    )
                    compactMetric(
                        title: "Threat rate",
                        value: formattedRatioPercent(service.activeThreatRateRatio),
                        detail: deltaText(
                            current: service.activeThreatRateRatio,
                            baseline: service.historicalBaseline.threatRate,
                            percentage: true
                        ),
                        tint: deviationTint(
                            current: service.activeThreatRateRatio,
                            baseline: service.historicalBaseline.threatRate
                        )
                    )
                }
            } else {
                Text("No active run selected. The strip will populate when {spot} has a live or selected run.")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(18)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 24))
    }

    private var compactColumns: [GridItem] {
        Array(repeating: GridItem(.flexible(minimum: 120), spacing: 10), count: 6)
    }

    @ViewBuilder
    private func compactMetric(title: String, value: String, detail: String, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 20, weight: .bold, design: .default))
                .foregroundStyle(tint)
                .lineLimit(1)
                .minimumScaleFactor(0.75)
            if !detail.isEmpty {
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(tint == .primary ? .secondary : tint.opacity(0.9))
                    .lineLimit(2)
                    .minimumScaleFactor(0.8)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 82, alignment: .leading)
        .padding(12)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 18))
    }

    private func deviationTint(current: Double?, baseline: Double?) -> Color {
        guard let current, let baseline, baseline > 0 else { return .primary }
        let ratio = (current - baseline) / baseline
        if ratio > 0.05 { return .orange }
        if ratio < -0.05 { return .teal }
        return .primary
    }

    private func deltaText(current: Double?, baseline: Double?, percentage: Bool) -> String {
        guard let current, let baseline, baseline > 0 else { return "all-time avg unavailable" }
        let delta = ((current - baseline) / baseline) * 100
        let sign = delta > 0 ? "+" : ""
        if percentage {
            return "\(sign)\(String(format: "%.1f", delta))% vs all-time avg"
        }
        return "\(sign)\(String(format: "%.1f", delta))% vs all-time avg"
    }

    private func stateTint(_ state: String) -> Color {
        switch state.uppercased() {
        case "PROCESSING", "STARTING", "WRITING":
            return .teal
        case "PAUSED":
            return .yellow
        case "FAILED", "CANCELLED":
            return .orange
        case "COMPLETED":
            return .green
        default:
            return .primary
        }
    }

    private func formattedInt(_ value: Int?) -> String {
        guard let value else { return "-" }
        return "\(value)"
    }

    private func formattedPercent(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "%.2f%%", value)
    }

    private func formattedRatioPercent(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "%.2f%%", value * 100)
    }

    private func formattedDecimal(_ value: Double?) -> String {
        guard let value else { return "-" }
        return String(format: "%.2f s", value)
    }
}
