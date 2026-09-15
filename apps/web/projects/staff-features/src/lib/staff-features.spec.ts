import { ComponentFixture, TestBed } from '@angular/core/testing';

import { StaffFeatures } from './staff-features';

describe('StaffFeatures', () => {
  let component: StaffFeatures;
  let fixture: ComponentFixture<StaffFeatures>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StaffFeatures],
    }).compileComponents();

    fixture = TestBed.createComponent(StaffFeatures);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
