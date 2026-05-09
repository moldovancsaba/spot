import SwiftUI

struct SpotMetricSparklineView: View {
    let values: [Double]
    let color: Color

    var body: some View {
        GeometryReader { proxy in
            let points = normalizedPoints(in: proxy.size)
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.white.opacity(0.02))

                if points.count > 1 {
                    Path { path in
                        path.move(to: points[0])
                        for point in points.dropFirst() {
                            path.addLine(to: point)
                        }
                    }
                    .stroke(color.opacity(0.9), style: StrokeStyle(lineWidth: 2.4, lineCap: .round, lineJoin: .round))
                } else if let point = points.first {
                    Circle()
                        .fill(color)
                        .frame(width: 6, height: 6)
                        .position(point)
                }
            }
        }
    }

    private func normalizedPoints(in size: CGSize) -> [CGPoint] {
        guard !values.isEmpty else { return [] }
        let minValue = values.min() ?? 0
        let maxValue = values.max() ?? 0
        let range = max(maxValue - minValue, 0.0001)
        let width = max(size.width, 1)
        let height = max(size.height, 1)

        return values.enumerated().map { index, value in
            let x = values.count == 1 ? width / 2 : (CGFloat(index) / CGFloat(max(values.count - 1, 1))) * width
            let normalized = (value - minValue) / range
            let y = height - (CGFloat(normalized) * (height - 8)) - 4
            return CGPoint(x: x, y: y)
        }
    }
}
