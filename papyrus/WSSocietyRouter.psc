Scriptname WSSocietyRouter extends Quest
; Original routing adapter. All alias objects stay inside Papyrus because the
; installed JavaScript bridge cannot convert returned ReferenceAlias objects.
FormList Property ResidentReference Auto
FormList Property DestinationReference Auto
GlobalVariable Property RequestSerial Auto
GlobalVariable Property AcknowledgedSerial Auto
GlobalVariable Property RouteStatus Auto
Float routeBegan = 0.0

Event OnInit()
    RegisterForSingleUpdate(0.25)
EndEvent

Event OnUpdate()
    If IsRunning()
        Int serial = RequestSerial.GetValue() as Int
        If serial > 0 && serial != (AcknowledgedSerial.GetValue() as Int)
            RouteStatus.SetValue(0.0)
            Actor resident = ResidentReference.GetAt(0) as Actor
            ObjectReference destination = DestinationReference.GetAt(0) as ObjectReference
            ReferenceAlias residentAlias = GetAlias(0) as ReferenceAlias
            ReferenceAlias destinationAlias = GetAlias(1) as ReferenceAlias
            If resident && destination && residentAlias && destinationAlias && resident != destination && !resident.IsDead() && !resident.IsChild()
                destinationAlias.ForceRefTo(destination)
                residentAlias.ForceRefTo(resident)
                routeBegan = Utility.GetCurrentRealTime()
                Utility.Wait(0.1)
                If IsRunning() && serial == (RequestSerial.GetValue() as Int)
                    If residentAlias.GetReference() == resident && destinationAlias.GetReference() == destination
                        resident.EvaluatePackage()
                        RouteStatus.SetValue(1.0)
                    Else
                        RouteStatus.SetValue(-1.0)
                        Stop()
                    EndIf
                    AcknowledgedSerial.SetValue(serial as Float)
                EndIf
            Else
                RouteStatus.SetValue(-1.0)
                AcknowledgedSerial.SetValue(serial as Float)
                Stop()
            EndIf
        ElseIf routeBegan > 0.0 && (Utility.GetCurrentRealTime() < routeBegan || Utility.GetCurrentRealTime() - routeBegan > 120.0)
            ; A disconnected controller cannot retain this package indefinitely.
            RouteStatus.SetValue(-2.0)
            Stop()
            routeBegan = 0.0
        ElseIf RouteStatus.GetValue() == 1.0
            ReferenceAlias activeResident = GetAlias(0) as ReferenceAlias
            ReferenceAlias activeDestination = GetAlias(1) as ReferenceAlias
            If !activeResident || !activeDestination
                RouteStatus.SetValue(-3.0)
                Stop()
            ElseIf activeResident.GetReference() != (ResidentReference.GetAt(0) as ObjectReference) || activeDestination.GetReference() != (DestinationReference.GetAt(0) as ObjectReference)
                RouteStatus.SetValue(-3.0)
                Stop()
            EndIf
        EndIf
    EndIf
    ; This lightweight native timer is not model inference. It also permits a
    ; stopped quest to restart without relying on OnInit being delivered twice.
    RegisterForSingleUpdate(0.5)
EndEvent
