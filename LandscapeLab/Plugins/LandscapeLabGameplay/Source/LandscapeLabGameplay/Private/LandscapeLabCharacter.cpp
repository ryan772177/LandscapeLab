// Copyright Ryan B. LandscapeLab.

#include "LandscapeLabCharacter.h"

#include "Animation/AnimInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"

ALandscapeLabCharacter::ALandscapeLabCharacter()
{
	// The capsule stays at ACharacter's own InitCapsuleSize(34, 88) from
	// Character.cpp:78 unless config overrides it. recipes/character.json
	// declares the same numbers; setting them again here would be a third
	// copy.

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	if (UCharacterMovementComponent* Move = GetCharacterMovement())
	{
		Move->bOrientRotationToMovement = true;
		Move->RotationRate = FRotator(0.0f, 500.0f, 0.0f);
	}

	// THE MESH OFFSET IS A STRUCTURAL FACT ABOUT THE UE MANNEQUIN, NOT A
	// SCENE PARAMETER, so it lives here rather than in the recipe: the
	// skeleton's origin is at the pelvis and it faces +Y, while a capsule is
	// centred and a pawn faces +X. -90 yaw and -HalfHeight Z is the standard
	// correction and is the same in every UE template.
	if (USkeletalMeshComponent* MeshComp = GetMesh())
	{
		MeshComp->SetRelativeLocationAndRotation(
			FVector(0.0f, 0.0f, -88.0f), FRotator(0.0f, -90.0f, 0.0f));
	}

	// The face component exists UNCONDITIONALLY and carries a mesh only when
	// FaceMeshPath resolves. Creating it conditionally is not available:
	// CreateDefaultSubobject runs during CDO construction, long before any
	// config is read, and a component that sometimes exists is a component
	// Blueprint reparenting and component-order assumptions cannot rely on.
	// Empty and attached costs nothing to render.
	FaceMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FaceMesh"));
	FaceMesh->SetupAttachment(GetMesh());

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 400.0f;
	CameraBoom->bUsePawnControlRotation = true;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;
}

void ALandscapeLabCharacter::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	Unresolved.Reset();
	ApplyConfiguredMovement();
	ApplyConfiguredAssets();
}

void ALandscapeLabCharacter::ApplyConfiguredMovement()
{
	// A zero means "not configured" and is SKIPPED, leaving the engine
	// default in place. It does not mean "set this to zero" -- a character
	// with MaxWalkSpeed 0 cannot move, and silently producing that from an
	// absent ini entry would look exactly like a physics bug.
	UCharacterMovementComponent* Move = GetCharacterMovement();
	UCapsuleComponent* Capsule = GetCapsuleComponent();
	if (!Move || !Capsule)
	{
		Unresolved.Add(TEXT("movement: no CMC or capsule"));
		return;
	}
	if (CfgMaxWalkSpeedCmS > 0.0f)      { Move->MaxWalkSpeed = CfgMaxWalkSpeedCmS; }
	if (CfgMaxStepHeightCm > 0.0f)      { Move->MaxStepHeight = CfgMaxStepHeightCm; }
	if (CfgJumpZVelocityCmS > 0.0f)     { Move->JumpZVelocity = CfgJumpZVelocityCmS; }
	if (CfgMaxAccelerationCmS2 > 0.0f)  { Move->MaxAcceleration = CfgMaxAccelerationCmS2; }
	if (CfgGravityScale > 0.0f)         { Move->GravityScale = CfgGravityScale; }
	if (CfgWalkableFloorAngleDeg > 0.0f)
	{
		// SetWalkableFloorAngle, not WalkableFloorAngle =. The setter also
		// recomputes WalkableFloorZ, which is the value the floor test
		// actually reads (CharacterMovementComponent.cpp:682 sets the pair
		// through SetWalkableFloorZ for the same reason). Assigning the angle
		// alone lands a correct-looking number that nothing consults.
		if (CfgWalkableFloorAngleDeg > 89.0f)
		{
			Unresolved.Add(FString::Printf(
				TEXT("CfgWalkableFloorAngleDeg=%.3f is >= vertical; refusing"),
				CfgWalkableFloorAngleDeg));
		}
		else
		{
			Move->SetWalkableFloorAngle(CfgWalkableFloorAngleDeg);
		}
	}
	if (CameraBoom)
	{
		if (CfgCameraArmLengthCm > 0.0f)
		{
			CameraBoom->TargetArmLength = CfgCameraArmLengthCm;
		}
		if (CfgCameraProbeSizeCm > 0.0f)
		{
			// The probe stays ENABLED. Disabling it was measured to put the
			// camera inside the canopy, which is worse than the close-up it
			// was meant to cure -- both were photographed on 2026-08-16.
			CameraBoom->bDoCollisionTest = true;
			CameraBoom->ProbeSize = CfgCameraProbeSizeCm;
		}
		if (CfgCameraSocketOffsetZCm > 0.0f)
		{
			CameraBoom->SocketOffset =
				FVector(0.0f, 0.0f, CfgCameraSocketOffsetZCm);
		}
	}

	if (CfgCapsuleRadiusCm > 0.0f && CfgCapsuleHalfHeightCm > 0.0f)
	{
		if (CfgCapsuleHalfHeightCm < CfgCapsuleRadiusCm)
		{
			Unresolved.Add(TEXT("capsule: half height below radius, not a capsule"));
		}
		else
		{
			Capsule->SetCapsuleSize(CfgCapsuleRadiusCm, CfgCapsuleHalfHeightCm);
		}
	}
}

void ALandscapeLabCharacter::ApplyConfiguredAssets()
{
	USkeletalMeshComponent* MeshComp = GetMesh();

	if (MeshPath.IsValid())
	{
		// Named LoadedMesh, not Mesh: ACharacter already has a member called
		// Mesh (Character.h:352) and shadowing it is a warning-as-error here.
		if (USkeletalMesh* LoadedMesh = Cast<USkeletalMesh>(MeshPath.TryLoad()))
		{
			if (MeshComp)
			{
				MeshComp->SetSkeletalMesh(LoadedMesh);
			}
		}
		else
		{
			// CONFIGURED BUT UNRESOLVABLE is a different fact from ABSENT,
			// and it is the one that means someone typed a path wrong.
			Unresolved.Add(FString::Printf(TEXT("MeshPath=%s"), *MeshPath.ToString()));
		}
	}

	if (FaceMeshPath.IsValid())
	{
		if (USkeletalMesh* LoadedFace = Cast<USkeletalMesh>(FaceMeshPath.TryLoad()))
		{
			if (FaceMesh && MeshComp)
			{
				FaceMesh->SetSkeletalMesh(LoadedFace);
				// ONE POSE, ONE AUTHORITY. The face must not run its own
				// animation graph -- a second independent evaluation of the
				// same character is how a head ends up looking somewhere the
				// body is not. SetLeaderPoseComponent maps follower bones to
				// the leader BY NAME, which is what MetaHuman's own actors
				// rely on and why the two different skeletons still track.
				FaceMesh->SetLeaderPoseComponent(MeshComp);
			}
			else
			{
				Unresolved.Add(TEXT("FaceMesh: component or body mesh missing"));
			}
		}
		else
		{
			// CONFIGURED BUT UNRESOLVABLE, which is a different fact from
			// ABSENT: absent means "this character has no face mesh", this
			// means "somebody typed a path wrong".
			Unresolved.Add(FString::Printf(TEXT("FaceMeshPath=%s"),
			                               *FaceMeshPath.ToString()));
		}
	}

	if (AnimClassPath.IsValid())
	{
		if (UClass* AnimClass = AnimClassPath.TryLoadClass<UAnimInstance>())
		{
			if (MeshComp)
			{
				MeshComp->SetAnimInstanceClass(AnimClass);
			}
		}
		else
		{
			Unresolved.Add(FString::Printf(TEXT("AnimClassPath=%s"),
			                               *AnimClassPath.ToString()));
		}
	}

	struct FBind { const FSoftObjectPath& Path; TObjectPtr<UInputAction>& Out; const TCHAR* Name; };
	const FBind Binds[] = {
		{ MoveActionPath, MoveAction, TEXT("MoveActionPath") },
		{ LookActionPath, LookAction, TEXT("LookActionPath") },
		{ JumpActionPath, JumpAction, TEXT("JumpActionPath") },
	};
	for (const FBind& B : Binds)
	{
		if (!B.Path.IsValid())
		{
			continue;
		}
		B.Out = Cast<UInputAction>(B.Path.TryLoad());
		if (!B.Out)
		{
			Unresolved.Add(FString::Printf(TEXT("%s=%s"), B.Name, *B.Path.ToString()));
		}
	}

	if (MappingContextPath.IsValid())
	{
		DefaultMappingContext = Cast<UInputMappingContext>(MappingContextPath.TryLoad());
		if (!DefaultMappingContext)
		{
			Unresolved.Add(FString::Printf(TEXT("MappingContextPath=%s"),
			                               *MappingContextPath.ToString()));
		}
	}

	if (Unresolved.Num() > 0)
	{
		UE_LOG(LogTemp, Warning,
		       TEXT("LandscapeLabCharacter: %d configured item(s) did not "
		            "resolve: %s"),
		       Unresolved.Num(), *FString::Join(Unresolved, TEXT(", ")));
	}
}

void ALandscapeLabCharacter::GetResolvedSpec(FString& OutMesh, FString& OutAnimClass,
                                             FString& OutMappingContext,
                                             int32& OutBoundActions,
                                             FString& OutUnresolved) const
{
	// Read the COMPONENTS, not the config fields that were used to set them.
	// Reading back MeshPath would only prove the ini parsed; this proves the
	// mesh is on the character (non-negotiable 8).
	OutMesh.Reset();
	OutAnimClass.Reset();
	// NOT declared const: USkeletalMeshComponent::GetAnimClass() is non-const
	// (SkeletalMeshComponent.h:1089). ACharacter::GetMesh() const already
	// hands back a non-const pointer, so nothing is being cast away here.
	if (USkeletalMeshComponent* MeshComp = GetMesh())
	{
		if (const USkeletalMesh* M = MeshComp->GetSkeletalMeshAsset())
		{
			OutMesh = M->GetPathName();
		}
		if (const UClass* AC = MeshComp->GetAnimClass())
		{
			OutAnimClass = AC->GetPathName();
		}
	}
	OutMappingContext = DefaultMappingContext ? DefaultMappingContext->GetPathName() : FString();
	OutBoundActions = (MoveAction ? 1 : 0) + (LookAction ? 1 : 0) + (JumpAction ? 1 : 0);
	OutUnresolved = FString::Join(Unresolved, TEXT(", "));
}

void ALandscapeLabCharacter::BeginPlay()
{
	Super::BeginPlay();

	if (!DefaultMappingContext)
	{
		UE_LOG(LogTemp, Log,
		       TEXT("LandscapeLabCharacter: no mapping context; player input "
		            "is inactive."));
		return;
	}
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Sub =
			    ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(
				    PC->GetLocalPlayer()))
		{
			Sub->AddMappingContext(DefaultMappingContext, 0);
		}
	}
}

void ALandscapeLabCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogTemp, Warning,
		       TEXT("LandscapeLabCharacter: input component is not an "
		            "UEnhancedInputComponent; no bindings made."));
		return;
	}

	if (JumpAction)
	{
		Input->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
		Input->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	}
	if (MoveAction)
	{
		Input->BindAction(MoveAction, ETriggerEvent::Triggered, this,
		                  &ALandscapeLabCharacter::Move);
	}
	if (LookAction)
	{
		Input->BindAction(LookAction, ETriggerEvent::Triggered, this,
		                  &ALandscapeLabCharacter::Look);
	}
}

void ALandscapeLabCharacter::ApplyMovementSpec(float MaxWalkSpeedCmS,
                                              float MaxStepHeightCm,
                                              float JumpZVelocityCmS,
                                              float MaxAccelerationCmS2,
                                              float GravityScale,
                                              float CapsuleRadiusCm,
                                              float CapsuleHalfHeightCm,
                                              bool& bOutSuccess,
                                              FString& OutError)
{
	bOutSuccess = false;
	OutError.Reset();

	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move)
	{
		OutError = TEXT("no CharacterMovementComponent on this character");
		return;
	}
	UCapsuleComponent* Capsule = GetCapsuleComponent();
	if (!Capsule)
	{
		OutError = TEXT("no CapsuleComponent on this character");
		return;
	}

	// REFUSE rather than clamp. A silently clamped value is a recipe that no
	// longer describes the character, and the recipe is the record.
	if (MaxWalkSpeedCmS <= 0.0f || MaxStepHeightCm < 0.0f
		|| MaxAccelerationCmS2 <= 0.0f || CapsuleRadiusCm <= 0.0f
		|| CapsuleHalfHeightCm <= 0.0f)
	{
		OutError = FString::Printf(
			TEXT("refusing a non-physical spec: speed=%.3f step=%.3f accel=%.3f "
			     "radius=%.3f halfheight=%.3f"),
			MaxWalkSpeedCmS, MaxStepHeightCm, MaxAccelerationCmS2,
			CapsuleRadiusCm, CapsuleHalfHeightCm);
		return;
	}
	if (CapsuleHalfHeightCm < CapsuleRadiusCm)
	{
		OutError = FString::Printf(
			TEXT("capsule half height %.3f is below its radius %.3f, which is "
			     "not a capsule"), CapsuleHalfHeightCm, CapsuleRadiusCm);
		return;
	}

	Move->MaxWalkSpeed = MaxWalkSpeedCmS;
	Move->MaxStepHeight = MaxStepHeightCm;
	Move->JumpZVelocity = JumpZVelocityCmS;
	Move->MaxAcceleration = MaxAccelerationCmS2;
	Move->GravityScale = GravityScale;
	Capsule->SetCapsuleSize(CapsuleRadiusCm, CapsuleHalfHeightCm);

	const bool bLanded =
		FMath::IsNearlyEqual(Move->MaxWalkSpeed, MaxWalkSpeedCmS, 1e-3f)
		&& FMath::IsNearlyEqual(Move->MaxStepHeight, MaxStepHeightCm, 1e-3f)
		&& FMath::IsNearlyEqual(Move->JumpZVelocity, JumpZVelocityCmS, 1e-3f)
		&& FMath::IsNearlyEqual(Move->MaxAcceleration, MaxAccelerationCmS2, 1e-3f)
		&& FMath::IsNearlyEqual(Move->GravityScale, GravityScale, 1e-3f)
		&& FMath::IsNearlyEqual(Capsule->GetUnscaledCapsuleRadius(), CapsuleRadiusCm, 1e-3f)
		&& FMath::IsNearlyEqual(Capsule->GetUnscaledCapsuleHalfHeight(), CapsuleHalfHeightCm, 1e-3f);

	if (!bLanded)
	{
		OutError = TEXT("a value did not read back equal after being set");
		return;
	}
	bOutSuccess = true;
}

void ALandscapeLabCharacter::Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller)
	{
		return;
	}
	// Move relative to where the camera is looking, flattened to the ground
	// plane -- otherwise looking down drives the character into the terrain.
	const FRotator YawOnly(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
	const FVector Forward = FRotationMatrix(YawOnly).GetUnitAxis(EAxis::X);
	const FVector Right = FRotationMatrix(YawOnly).GetUnitAxis(EAxis::Y);
	AddMovementInput(Forward, Axis.Y);
	AddMovementInput(Right, Axis.X);
}

void ALandscapeLabCharacter::Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!Controller)
	{
		return;
	}
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(Axis.Y);
}
