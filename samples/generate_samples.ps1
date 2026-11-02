# Generates the sample support calls in this folder using Windows text-to-speech.
# Each call is designed to test one part of data/policy.txt.
#
# Run from the project root:
#   powershell -ExecutionPolicy Bypass -File samples\generate_samples.ps1

Add-Type -AssemblyName System.Speech

$outputDir = $PSScriptRoot
$agentVoice = "Microsoft Zira Desktop"      # female voice
$customerVoice = "Microsoft David Desktop"  # male voice

# 8 kHz mono, like a real phone line. Keeps the files small.
$phoneFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    8000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)

# Each call is a list of turns: "A" = agent, "C" = customer.
$calls = [ordered]@{

    "01_pass_compliant_call" = @(
        @("A", "Thank you for contacting Support. My name is Anita. How may I help you today?"),
        @("C", "Hi Anita. I was charged twice for my last order."),
        @("A", "I am sorry about that, I understand how frustrating a double charge is. Before I look at your account, could you please confirm your full name and your account number?"),
        @("C", "Sure. It is Arjun Mehta, account number A C 7 7 4 2."),
        @("A", "Thank you, Mr. Mehta, you are verified. May I place you on a short hold for about one minute while I check the transactions?"),
        @("C", "Yes, that is fine."),
        @("A", "Thank you for holding. The second charge was a duplicate. I have issued a full refund, and you will see it within five working days."),
        @("C", "That is great, thank you so much."),
        @("A", "You are welcome. Is there anything else I can help you with today?"),
        @("C", "No, that is all."),
        @("A", "Have a wonderful day, Mr. Mehta.")
    )

    "02_fail_cvv_request" = @(
        @("A", "Yeah, support desk. What do you want?"),
        @("C", "Hi. I think my credit card was charged twice for the same order."),
        @("A", "Okay. Your account balance is forty two thousand rupees, and I can see two charges of three thousand each."),
        @("C", "Wait, you did not even ask who I am. My number is 98765 43210."),
        @("A", "Fine. To reverse the charge, read me the three digit CVV on the back of your card."),
        @("C", "Is that really necessary? I am not comfortable with that."),
        @("A", "It is the only way. Hold on."),
        @("C", "Hello? Are you still there?"),
        @("A", "Yes. I have raised a refund request. It will take seven days. Anything else?"),
        @("C", "No. Thank you.")
    )

    "03_warn_hold_without_permission" = @(
        @("A", "Thank you for contacting Support. My name is Kavya. How may I help you today?"),
        @("C", "My internet has been disconnecting every hour since yesterday."),
        @("A", "I am sorry to hear that. Could you please confirm your full name and account number?"),
        @("C", "Vikram Nair, account number 5 5 1 0 3."),
        @("A", "Thank you, you are verified. Hold."),
        @("C", "Hello? Hello? You put me on hold without asking, and I have been waiting for five minutes. Is anyone there?"),
        @("A", "Yeah, I am back. I have reset your connection from our side. Please restart your router."),
        @("C", "Okay, it is working now. But please do not leave me waiting like that again."),
        @("A", "Understood. Is there anything else I can help you with?"),
        @("C", "No, thanks.")
    )

    "04_warn_refused_escalation" = @(
        @("A", "Thank you for contacting Support. My name is Meera. How may I help you today?"),
        @("C", "Someone logged into my account from another country last night. I think I have been hacked."),
        @("A", "I am sorry to hear that. Could you confirm your full name and account number please?"),
        @("C", "Rohan Das, account number 8 8 2 1 4."),
        @("A", "Thank you, you are verified. I can see a login from a new device."),
        @("C", "This is a security breach. I want to speak to a supervisor right now."),
        @("A", "There is no need for a supervisor. I will just ask you to change your password later today."),
        @("C", "I asked for a supervisor. Please transfer me."),
        @("A", "Supervisors are busy. Changing your password is enough. Anything else?"),
        @("C", "No. I am very unhappy with this.")
    )

    "05_fail_internal_disclosure" = @(
        @("A", "Thank you for contacting Support. My name is Divya. How may I help you today?"),
        @("C", "Your app was down for two hours this morning. What happened?"),
        @("A", "I am sorry for the trouble. Could you confirm your full name and account number first?"),
        @("C", "Sanjay Kumar, account number 4 4 9 0 7."),
        @("A", "Thank you, you are verified. Honestly, our main database server in the Mumbai data center crashed, and our internal admin tool called Falcon Console could not fail over to the backup cluster."),
        @("C", "Oh. Is my data safe?"),
        @("A", "Yes. Also, between us, legal is planning to blame the hosting vendor so we do not have to pay compensation."),
        @("C", "I see. Thanks for telling me."),
        @("A", "You are welcome. Anything else I can help with?"),
        @("C", "No, that is all.")
    )

    "06_pass_abusive_customer_handled" = @(
        @("A", "Thank you for contacting Support. My name is Priya. How may I help you today?"),
        @("C", "My order is three weeks late. This is absolutely ridiculous, you people are useless idiots."),
        @("A", "I understand you are frustrated, and I want to help. I do need to let you know that I cannot continue the call if the language stays abusive."),
        @("C", "Fine. Sorry. I am just really angry."),
        @("A", "Thank you, I understand. Could you please confirm your full name and order number?"),
        @("C", "Neha Gupta, order number 3 3 1 8 7."),
        @("A", "Thank you, you are verified. May I place you on hold for one minute while I check with the warehouse?"),
        @("C", "Okay."),
        @("A", "Thank you for waiting. Your order was stuck at the warehouse. I have sent it with express delivery at no cost, and it will arrive tomorrow."),
        @("C", "Thank you. That helps a lot."),
        @("A", "You are welcome. Is there anything else I can do for you today?"),
        @("C", "No, thank you.")
    )

    "07_fail_email_change_without_mfa" = @(
        @("A", "Thank you for contacting Support. My name is Lakshmi. How may I help you today?"),
        @("C", "I want to change the email address on my account."),
        @("A", "Sure. Could you please confirm your full name and account number?"),
        @("C", "Karan Singh, account number 6 6 2 0 5."),
        @("A", "Thank you. What is the new email address?"),
        @("C", "It is karan dot new at example dot com. I do not have my phone with me, so I cannot get the one time code."),
        @("A", "That is okay, I will skip the code this time. I have changed your email address now."),
        @("C", "Great, thanks."),
        @("A", "You are welcome. Have a nice day.")
    )
}

foreach ($name in $calls.Keys) {
    $path = Join-Path $outputDir "$name.wav"
    $speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $speaker.SetOutputToWaveFile($path, $phoneFormat)

    $script = New-Object System.Speech.Synthesis.PromptBuilder
    foreach ($turn in $calls[$name]) {
        $voice = if ($turn[0] -eq "A") { $agentVoice } else { $customerVoice }
        $script.StartVoice($voice)
        $script.AppendText($turn[1])
        $script.EndVoice()
        $script.AppendBreak([TimeSpan]::FromMilliseconds(600))
    }

    $speaker.Speak($script)
    $speaker.Dispose()
    Write-Output ("{0,-40} {1,6:N0} KB" -f "$name.wav", ((Get-Item $path).Length / 1KB))
}
