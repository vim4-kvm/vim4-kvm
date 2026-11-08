import Carbon
import Foundation
func identifier(_ source:TISInputSource)->String {
    let value=TISGetInputSourceProperty(source,kTISPropertyInputSourceID)!
    return Unmanaged<CFString>.fromOpaque(value).takeUnretainedValue() as String
}
let original=identifier(TISCopyCurrentKeyboardInputSource().takeRetainedValue())
if CommandLine.arguments.count==2 {
    let target=CommandLine.arguments[1]
    let values=TISCreateInputSourceList(nil,false).takeRetainedValue() as! [TISInputSource]
    guard let source=values.first(where:{identifier($0)==target}),TISSelectInputSource(source)==noErr else {fatalError("Input source not available: \(target)")}
}
print(identifier(TISCopyCurrentKeyboardInputSource().takeRetainedValue()))

